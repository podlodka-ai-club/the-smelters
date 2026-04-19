Project: DemoApp

# Advanced Filtering & Sorting

## Summary

- Priority: High
- Estimated Duration: 1-2 days
- Complexity: Low-Medium
- User Impact: Medium

## Context

Add content filters, language preferences, and content type options to search results. This feature enables:
- **Content Control**: Filter by age-appropriate ratings (G, PG, PG-13, R)
- **Localization**: Search in preferred languages
- **Content Type Filtering**: Filter between GIFs, clips, stickers
- **Persistent Preferences**: Remember user filter settings
- **Safer Browsing**: Parents/schools can enforce content restrictions
- **Faster Discovery**: Find relevant content without scrolling

### User Stories

1. **As a user**, I want to **filter search results by content rating**, so I can **find age-appropriate content**
2. **As a user**, I want to **set my preferred language**, so I can **get results in my language**
3. **As a user**, I want to **filter by content type** (GIFs, clips, stickers), so I can **find exactly what I need**
4. **As a user**, I want my **filter preferences to persist**, so I don't **have to set them every time**
5. **As a parent**, I want to **restrict content to G-rated only**, so I can **protect my child from inappropriate content**
6. **As a user**, I want to **see active filters clearly**, so I can **understand what filters are applied**

---

## Technical Notes

### Dependencies

**DataStore Preferences** for lightweight persistent preferences:
- `androidx.datastore:datastore-preferences` (1.0.0+)

### Architecture

Following the modular Clean Architecture pattern:

```
domain/filtering/
├── model/           ← Filter models & enums
├── repository/      ← Repository interfaces
├── usecase/         ← Business logic
└── di/              ← DI registration

data/filtering/
├── local/           ← DataStore preferences wrapper
├── mapper/          ← Data transformation
├── repository/      ← Repository implementations
└── di/              ← DI registration

feature/search/
├── SearchScreen.kt  ← Enhanced with filter UI (chips, dialog)
├── SearchViewModel  ← Enhanced with filter state
└── SearchModule.kt  ← No changes (DI in domain/data modules)
```

### Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Preferences** | DataStore | Lightweight persistent preferences |
| **State** | StateFlow | Reactive filter state |
| **DI** | Koin | Dependency injection |
| **UI** | Jetpack Compose | Filter dialog and chips |
| **Coroutines** | Kotlin Coroutines | Async preference operations |

---

## Implementation Plan

### Phase 1: Domain Layer (Day 1)

Define filter models and business logic:

- **Create domain models** (`domain/filtering/model/`)
  - Define `ContentRating` enum with values: ALL, G, PG, PG-13, R (include API values)
  - Define `ContentBundle` enum with values: ALL, CLIPS, STICKERS, CLIPS_AND_STICKERS
  - Create `FilterOptions` data class with: contentRating, language, contentBundle, isActive flag
  - Map enums to Giphy API parameters (e.g., "pg-13" for API)

- **Create repository interface** (`domain/filtering/repository/`)
  - `FilterPreferencesRepository` with methods for: get filters, save filters, reset filters

- **Create use cases** (`domain/filtering/usecase/`)
  - `GetFilterPreferencesUseCase`: Fetch current filter preferences as Flow
  - `SaveFilterPreferencesUseCase`: Save user-selected filters
  - `ResetFiltersUseCase`: Reset to default (all) filters

### Phase 2: Data Layer (Day 1)

Implement preferences persistence:

- **Create DataStore wrapper** (`data/filtering/local/`)
  - Use Preferences DataStore (simpler than Proto)
  - Define preference keys for: rating, language, bundle
  - Methods to: read preferences, write preferences, clear all
  - Handle deserialization of enum values from strings

- **Create mappers** (`data/filtering/mapper/`)
  - Convert between DataStore strings and domain enums
  - Handle API value conversions

- **Create repository implementation** (`data/filtering/repository/`)
  - Implement `FilterPreferencesRepository` using DataStore
  - Return Flow for reactive preference updates
  - Handle errors gracefully with defaults

### Phase 3: Feature Layer (Day 2)

Enhance Search screen with filter UI:

- **Update SearchViewModel**
  - Add filter-related state: current filters, show filter dialog flag
  - Inject filter use cases
  - Handle filter changes: save preferences, refresh search results
  - Load saved filters on initialization

- **Update SearchScreen composable**
  - Add filter button to search field (with active indicator badge)
  - Show filter chips below search field when filters are active
  - Implement filter dialog with radio button options for:
    - Content rating (ALL, G, PG, PG-13, R)
    - Language (English, Spanish, French, German, Japanese, Korean, etc.)
    - Content bundle (ALL, Clips, Stickers)
  - Add reset button to clear all filters
  - Show count of active filters

- **Filter chips display**
  - Show selected filters as dismissible chips
  - Tapping chip removes that specific filter
  - Colored to indicate active state

- **Filter dialog**
  - Dialog format with sections for each filter type
  - Radio buttons for mutually exclusive options
  - Reset and Apply buttons at bottom
  - Proper spacing and typography

### Phase 4: Dependency Injection & Integration (Day 2)

Set up module registration:

- **Create domain module** with use case registrations
- **Create data module** with DataStore and repository registrations
- **Update `AppModule`** to include new modules
- **Update SearchViewModel DI** to inject filter use cases
- **Extend SearchGifsUseCase** to accept and apply filters to API calls

---

## Filter Models

### ContentRating Enum

Values and API mappings:
- `ALL` (API: "") - Show all ratings
- `G` (API: "g") - General Audiences
- `PG` (API: "pg") - Parental Guidance
- `PG_13` (API: "pg-13") - Parents Strongly Cautioned
- `R` (API: "r") - Restricted

Each enum should include:
- Display name for UI
- API value for Giphy API calls

### ContentBundle Enum

Values and API mappings:
- `ALL` (API: "") - All content types
- `CLIPS` (API: "clips_all") - Video clips only
- `STICKERS` (API: "stickers") - Stickers only
- `CLIPS_AND_STICKERS` (API: "clips_and_stickers") - Both

### FilterOptions Data Class

Fields:
- `contentRating`: ContentRating (default ALL)
- `language`: String ISO 639-1 code (default "en")
- `contentBundle`: ContentBundle (default ALL)
- `isActive`: Boolean (true if any non-default filter)

Method: `hasActiveFilters()` returns true if any filter differs from default

---

## Language Support

### Recommended Languages (12+ options)

- en (English)
- es (Spanish)
- fr (French)
- de (German)
- it (Italian)
- pt (Portuguese)
- ja (Japanese)
- ko (Korean)
- zh (Chinese)
- ru (Russian)
- ar (Arabic)
- hi (Hindi)

Display localized language names using Locale class.

---

## UI/UX Details

### Filter Button

Search field trailing area shows:
- Filter icon
- Badge indicator if filters are active (e.g., colored dot or number)
- Tap opens filter dialog

### Filter Chips Display

Below search field when active:
- Horizontal scrollable row of chips
- Each chip shows: filter type + value + close icon (✕)
- Tap close icon removes that filter
- Colored to indicate type (rating, language, bundle)

### Filter Dialog Layout

Modal dialog with sections:

**Content Rating Section:**
- Title: "Content Rating"
- Radio buttons: ALL, G, PG, PG-13, R
- Currently selected option highlighted

**Language Section:**
- Title: "Language"
- Radio buttons: Common languages (12+)
- Show localized language names
- Currently selected highlighted

**Content Type Section:**
- Title: "Content Type"
- Radio buttons: All GIFs, Clips, Stickers, Clips & Stickers
- Currently selected highlighted

**Action Buttons:**
- "Reset" button: Clear all filters to defaults
- "Apply" button: Save and close dialog

---

## API Integration

### Giphy API Filter Parameters

The Giphy API already supports these parameters:

- `rating`: Filter by content rating (g, pg, pg-13, r, empty for all)
- `lang`: Language preference (ISO 639-1 code, default en)
- `bundle`: Content type (clips_all, stickers, clips_and_stickers, empty for all)

### Implementation

Update existing `SearchGifsUseCase` to:
- Accept optional `FilterOptions` parameter
- Default to saved preferences from DataStore
- Pass filter values to API calls via repository

No API endpoint changes needed - just add parameters to existing calls.

---

## Data Persistence

### DataStore Storage

Store as preferences with keys:
- `"content_rating"` → String (API value)
- `"language"` → String (ISO code)
- `"content_bundle"` → String (API value)

Auto-persist on save, auto-load on app start.

### Default Behavior

- First launch: All filters set to "ALL" (no restriction)
- Subsequent launches: Load saved preferences
- User resets: Clear all preferences, default to "ALL"

---

## Performance Considerations

### Lightweight Storage

- DataStore is fast and lightweight
- No database overhead
- Direct preference access without Room

### Query Efficiency

- Filters applied at API call time
- No local filtering needed
- Giphy API handles filtering server-side

### Memory Usage

- Filter preferences tiny (few strings)
- No caching needed
- Real-time preference updates via Flow

---

## Coding Conventions Alignment

✅ **Clean Architecture**: Separate domain/data layers
✅ **MVVM Pattern**: StateFlow-based filter state
✅ **Functional Programming**: Map operations on enums
✅ **DI Pattern**: Koin modules with proper registration
✅ **DataStore**: Preferences-based persistence
✅ **Compose UI**: Stateless dialog/chip components
✅ **Coroutines**: viewModelScope for preference operations
✅ **Enums**: Type-safe filter values

---

## Testing Strategy

- Unit tests for each use case
- Unit tests for ViewModel filter management
- Integration tests for DataStore repository
- UI tests for filter dialog interactions
- Test filter application in search results
- Mock DataStore for isolated testing

---

## Success Criteria

✅ Filter dialog opens/closes properly
✅ Users can select content rating
✅ Users can select language
✅ Users can select content type
✅ Filter preferences persist across sessions
✅ Active filters display as dismissible chips
✅ Tapping chip removes that filter
✅ Reset button clears all filters
✅ Search results update with applied filters
✅ Filter preferences load on startup

---

## Future Enhancements

- 🎨 **Advanced Filters**: Duration, trending, upload date
- 📊 **Filter Suggestions**: Smart filter recommendations
- 📱 **Responsive UI**: Better tablet layout
- 🌍 **More Languages**: Add additional language options
- 👨‍👩‍👧‍👦 **Parental Controls**: Lock filters for kids' profiles
- 🔔 **Filter Presets**: Save custom filter combinations
- ⭐ **Trending Filters**: Show trending content filters
- 🎯 **Saved Searches**: Save queries with associated filters
