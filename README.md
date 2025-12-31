# zim-daily

A Daily log plugin derived from the built in Journal plugin

## Changes from Journal Plugin

### Core Functionality
- **Renamed from Journal to Daily**: All class names, functions, and UI elements updated
- **Day-only granularity**: Removed week/month/year options, exclusively uses daily pages
- **Updated copyright**: Changed to 2025-2026 TerseSquirrel-dev with proper attribution

### Path Structure Changes
- **New page format**: Changed from `YYYY:MM:DD` to `YYYY-MM-DD DayName` (e.g., "2025-12-30 Tuesday")
- **Hierarchical organization**: Pages now organized as `:Daily/YYYY:MM Month/Date DayName`
- **Month namespaces**: Each month gets its own namespace (e.g., `2025:12 December`)

### Configuration Changes
- **Removed granularity preferences**: No more day/week/month/year selection
- **Added template option**: Configurable template for daily pages (default: "Default")
- **Updated default namespace**: Changed from `:Journal` to `:Daily`
- **Simplified plugin properties**: Streamlined to daily-specific options

### Code Improvements
- **Simplified date parsing**: `daterange_from_path()` only handles day format with regex `YYYY-MM-DD \w+`
- **Removed unused imports**: Eliminated `weekcalendar` and other granularity-related imports
- **Updated template context**: Changed from `journal_plugin` to `daily_plugin` context variable
- **Streamlined anchor format**: Updated from ISO date to `YYYY-MM-DD DayName` format
- **Fixed date label format**: Simplified from full weekday name to date-only display

### UI Changes
- **Updated pane title**: Changed from "_Journal" to "D_aily" (with mnemonic)
- **Updated menu items**: Changed references from "Journal" to "Daily"
- **Simplified calendar widget**: Removed year-specific handling logic

### Technical Details
- **File size reduction**: Reduced from 448 to 406 lines (~9% reduction)
- **Logger name changed**: From `zim.plugins.journal` to `zim.plugins.daily`
- **Removed complexity**: Eliminated multi-granularity path matching and week handling
- **Template return**: Dynamic template selection based on properties instead of hardcoded 'Journal'
