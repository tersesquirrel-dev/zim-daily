# zim-daily

A Daily log plugin derived from the built in Journal plugin

## Changes

- Renamed from Journal to Daily
- Removed week/month/year granularity options 
- Plugin now assumes Day granularity exclusively
- Simplified path generation (`%Y:%m:%d`)
- Removed granularity-related preferences and properties
- Streamlined `daterange_from_path()` for day-only logic
- Removed unused imports (`weekcalendar`, etc.)
