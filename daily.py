# Copyright 2025-2026 TerseSquirrel-dev <tersesquirrel@gmail.com>
#
# Modified from original version by ...
#
# Copyright 2009-2018 Jaap Karssenberg <jaap.karssenberg@gmail.com>


from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk

import re

from functools import partial

import logging

from zim.plugins import PluginClass
from zim.actions import action
from zim.signals import SignalHandler, ConnectorMixin
import zim.datetimetz as datetime
from zim.notebook import Path, NotebookExtension
from zim.notebook.index import IndexNotFoundError
from zim.templates.expression import ExpressionFunction

from zim.gui.notebookview import NotebookViewExtension
from zim.gui.widgets import ScrolledWindow, \
	WindowSidePaneWidget, LEFT_PANE, PANE_POSITIONS

from zim.plugins.pageindex import PageTreeStore, PageTreeView


logger = logging.getLogger('zim.plugins.daily')


# FUTURE: Use calendar.HTMLCalendar from core libs to render this plugin in www

# TODO: add extension
# - hook to the pageview end-of-word signal and link dates
#   add a preference for this
# - Overload the "Insert date" dialog by adding a 'link' option


KEYVALS_ENTER = list(map(Gdk.keyval_from_name, ('Return', 'KP_Enter', 'ISO_Enter')))
KEYVALS_SPACE = (Gdk.unicode_to_keyval(ord(' ')),)

date_path_re = re.compile(r'^\d{4}-\d{2}-\d{2} \w+$')


def daterange_from_path(path):
	'''Determine the calendar dates mapped by a specific page
	@param path: a L{Path} object
	@returns: a 3-tuple of:
	  - the page type (one of "C{day}")
	  - a C{datetime.date} object for the start date
	  - a C{datetime.date} object for the end date
	or C{None} when the page does not map a date
	'''
	if date_path_re.match(path.name):
		# Parse format: YYYY-MM-DD DayName
		date_part = path.name.split(' ')[0]  # Get YYYY-MM-DD part
		year, month, day = list(map(int, date_part.split('-')))
		try:
			date = datetime.date(year, month, day)
		except ValueError:
			return None # not a valid date
		end_date = date
	else:
		return None # Not a daily path
	return type, date, end_date


class DailyPlugin(PluginClass):

	plugin_info = {
		'name': _('Daily'), # T: plugin name
		'description': _('''\
This plugin turns one section of the notebook into a daily log
with a page per day.
Also adds a calendar widget to access these pages.
'''),
		# T: plugin description
		'author': 'TerseSquirrel',
		'help': 'Plugins:Daily',
	}

	plugin_preferences = (
		# key, type, label, default
		('pane', 'choice', _('Position in the window'), LEFT_PANE, PANE_POSITIONS), # T: preferences option
		('hide_if_empty', 'bool', _('Hide Daily pane if empty'), False), # T: preferences option
	)

	plugin_notebook_properties = (
		('namespace', 'namespace', _('Section'), Path(':Daily')), # T: input label
	)

	def path_from_date(self, notebook, date):
		'''Returns the path for a daily page for a specific date'''
		properties = self.notebook_properties(notebook)
		month_namespace = date.strftime('%Y:%m %B')
		daily_page = date.strftime('%Y-%m-%d %A')
		return properties['namespace'].child(month_namespace).child(daily_page)

	def path_for_month_from_date(self, notebook, date):
		'''Returns the namespace path for a certain month'''
		properties = self.notebook_properties(notebook)
		return properties['namespace'].child(date.strftime('%Y:%m %B'))

	def date_from_path(self, path):
		'''Returns the date for a specific path or C{None}'''
		dates = daterange_from_path(path)
		if dates:
			return dates[1]
		else:
			return None


def dateRangeTemplateFunction(startdate, enddate):
	'''Returns a function to be used in templates to iterate a range of dates'''

	@ExpressionFunction
	def date_range_function(first=None, last=None):
		# first and last are integer offsets from the start
		oneday = datetime.timedelta(days=1)
		nextdate = startdate + datetime.timedelta(days=first) if first else startdate
		myenddate = startdate + datetime.timedelta(days=last) if last else enddate
		while nextdate <= myenddate:
			yield nextdate
			nextdate += oneday

	return date_range_function


class DailyNotebookExtension(NotebookExtension):
	'''Extend notebook by setting special page template for
	the daily pages namespace and by adding a hook to suggests links
	for dates.
	'''

	def __init__(self, plugin, notebook):
		NotebookExtension.__init__(self, plugin, notebook)
		self.connectto_all(
			notebook, ('suggest-link', 'get-page-template', 'init-page-template')
		)

	def on_suggest_link(self, notebook, source, text):
		#~ if date_path_re.match(path.text):
		#~ 	return Path(text)
		if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
			year, month, day = text.split('-')
			year, month, day = list(map(int, (year, month, day)))
			date = datetime.date(year, month, day)
			return self.plugin.path_from_date(notebook, date)
		# TODO other formats
		else:
			return None

	def on_get_page_template(self, notebook, path):
		properties = self.plugin.notebook_properties(notebook)
		if path.ischild(properties['namespace']) and daterange_from_path(path):
			# TODO: Check if daily file exists and if not create it with default formatting
			return 'Daily'
		else:
			return None

	def on_init_page_template(self, notebook, path, template):
		daterange = daterange_from_path(path)
		if daterange:
			self.connectto(template, 'process',
				partial(
					self.on_process_new_page_template,
					daterange=daterange
				)
			)

	def on_process_new_page_template(self, template, output, context, daterange):
		'''Callback called when parsing a template, e.g. when exporting
		a page or when a new page is created.
		Sets parameters in the template dict to be used in the template.
		'''
		type, start, end = daterange
		context['daily_plugin'] = {
			'page_type': type,
			'date': start,
			'start_date': start,
			'end_date': end,
			'days': dateRangeTemplateFunction(start, end),
		}


class DailyNotebookViewExtension(NotebookViewExtension):
	'''Extension used to add calendar dialog to mainwindow'''

	def __init__(self, plugin, pageview):
		NotebookViewExtension.__init__(self, plugin, pageview)

		self.notebook = pageview.notebook
		self.calendar_widget = CalendarWidget(plugin, self.notebook, self.navigation)
		self.connectto(pageview, 'page-changed', lambda o, p: self.calendar_widget.set_page(p))
		if pageview.page is not None:
			self.calendar_widget.set_page(pageview.page)

		properties = self.plugin.notebook_properties(self.notebook)
		self.connectto(properties, 'changed', self.on_properties_changed)
		self.on_properties_changed(properties)

	def on_properties_changed(self, properties):
		old_model = self.calendar_widget.treeview.get_model()
		self.disconnect_from(old_model)

		index = self.notebook.index
		namespace = properties['namespace']
		new_model = PageTreeStore(index, root=namespace, reverse=True)
		self.calendar_widget.treeview.set_model(new_model)

		self.connectto_all(new_model, ('row-inserted', 'row-deleted'), handler=self.on_pane_changed)
		self.on_pane_changed()

	def on_pane_changed(self, *a):
		show_pane = self._check_show_pane()
		widget_visible = self.calendar_widget.get_parent() is not None
		if show_pane and not widget_visible:
			self.add_sidepane_widget(self.calendar_widget, 'pane')
		elif not show_pane and widget_visible:
			self.remove_sidepane_widget(self.calendar_widget)

	def _check_show_pane(self):
		if self.plugin.preferences['hide_if_empty']:
			model = self.calendar_widget.treeview.get_model()
			n_pages = model.iter_n_children(None)
			return n_pages > 0
		else:
			return True

	@action(_('To_day'), accelerator='<Alt>D', menuhints='go') # T: menu item
	def go_page_today(self):
		today = datetime.date.today()
		path = self.plugin.path_from_date(self.pageview.notebook, today)
		anchor = today.strftime('%Y-%m-%d %A')  # e.g., "2025-12-30 Tuesday"
		self.navigation.open_page(path, anchor, anchor_fail_silent=True)


class Calendar(Gtk.Calendar):
	'''Custom calendar widget class. Adds an 'activate' signal for when a
	date is selected explicitly by the user.
	'''

	# define signals we want to use - (closure type, return type and arg types)
	__gsignals__ = {
		'activate': (GObject.SignalFlags.RUN_LAST, None, ()),
	}

	def __init__(self):
		GObject.GObject.__init__(self)
		self.selected = False

	def do_key_press_event(self, event):
		handled = Gtk.Calendar.do_key_press_event(self, event)
		if handled and (event.keyval in KEYVALS_SPACE
		or event.keyval in KEYVALS_ENTER):
			self.emit('activate')
		return handled

	def do_button_press_event(self, event):
		handled = Gtk.Calendar.do_button_press_event(self, event)
		if event.button == 1 and self.selected:
			self.selected = False
			self.emit('activate')
		return handled

	def do_day_selected(self):
		self.selected = True

	def select_date(self, date):
		'''Set selected date using a datetime oject'''
		self.select_month(date.month - 1, date.year)
		self.select_day(date.day)

	def get_date(self):
		'''Get the datetime object for the selected date'''
		year, month, day = Gtk.Calendar.get_date(self)
		if day == 0:
			day = 1

		try:
			date = datetime.date(year, month + 1, day)
		except ValueError:
			# This error may mean that day number is higher than allowed.
			# If so, set date to the last day of the month.
			if day > 27:
				date = datetime.date(year, month + 2, 1) - datetime.timedelta(days = 1)
			else:
				raise
		return date


class CalendarWidget(Gtk.VBox, WindowSidePaneWidget):

	title = _('_Daily') # T: side pane title

	def __init__(self, plugin, notebook, navigation):
		GObject.GObject.__init__(self)
		self.plugin = plugin
		self.notebook = notebook
		self.navigation = navigation
		self.model = CalendarWidgetModel(plugin, notebook)

		self.label_box = Gtk.HBox()
		self.pack_start(self.label_box, False, True, 0)

		self.label = Gtk.Label()
		button = Gtk.Button()
		button.add(self.label)
		button.set_relief(Gtk.ReliefStyle.NONE)
		button.connect('clicked', lambda b: self.go_today())
		self.label_box.add(button)

		self._close_button = None

		self._refresh_label()
		self._timer_id = \
			GObject.timeout_add(300000, self._refresh_label)
			# 5 minute = 300_000 ms
			# Ideally we only need 1 timer per day at 00:00, but not
			# callback for that
		self.connect('destroy',
			lambda o: GObject.source_remove(o._timer_id))
			# Clear reference, else we get a new timer for every dialog

		self.calendar = Calendar()
		self.calendar.set_display_options(
			Gtk.CalendarDisplayOptions.SHOW_HEADING |
			Gtk.CalendarDisplayOptions.SHOW_DAY_NAMES |
			Gtk.CalendarDisplayOptions.SHOW_WEEK_NUMBERS
		)
		self.calendar.connect('activate', self.on_calendar_activate)
		self.calendar.connect('month-changed', self.on_month_changed)
		self.on_month_changed(self.calendar)
		self.pack_start(self.calendar, False, True, 0)

		self.treeview = PageTreeView(notebook, navigation)
		self.pack_start(ScrolledWindow(self.treeview), True, True, 0)

	def go_today(self):
		self.calendar.select_date(datetime.date.today())
		self.calendar.emit('activate')

	def set_embeded_closebutton(self, button):
		if self._close_button:
			self.label_box.remove(self._close_button)

		if button is not None:
			self.label_box.pack_end(button, False, True, 0)

		self._close_button = button
		return True

	def _refresh_label(self, *a):
		#print "UPDATE LABEL %s" % id(self)
		format = _('%d %B %Y').replace(' 0', ' ')
			# T: strftime format for current date label
		text = datetime.strftime(format, datetime.date.today())
		self.label.set_text(text)
		return True # else timer is stopped

	def on_calendar_activate(self, calendar):
		date = calendar.get_date()
		path = self.plugin.path_from_date(self.notebook, date)
		self.navigation.open_page(path)

	def on_month_changed(self, calendar):
		calendar.clear_marks()
		for date in self.model.list_dates_for_month(self.calendar.get_date()):
			calendar.mark_day(date.day)

	def set_page(self, page):
		treepath = self.treeview.set_current_page(page, vivificate=True)
		if treepath:
			self.treeview.select_treepath(treepath)

		dates = daterange_from_path(page)
		if dates:
			cur_date = self.calendar.get_date()
			if cur_date < dates[1] or cur_date > dates[2]:
				self.calendar.select_date(dates[1])
		else:
			self.calendar.select_day(0)
			self.treeview.get_selection().unselect_all()


class CalendarWidgetModel(object):

	def __init__(self, plugin, notebook):
		self.plugin = plugin
		self.notebook = notebook

	def list_dates_for_month(self, date):
		namespace = self.plugin.path_for_month_from_date(self.notebook, date)
		try:
			for path in self.notebook.pages.list_pages(namespace):
				if date_path_re.match(path.name):
					dates = daterange_from_path(path)
					if dates and dates[0] == 'day':
						yield dates[1]
		except IndexNotFoundError:
			pass