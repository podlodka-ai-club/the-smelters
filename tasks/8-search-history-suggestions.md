Project: DemoApp

# Task 8: Search History & Suggestions

## Summary

- Priority: High
- Estimated Duration: 1-2 days
- Complexity: Low-Medium
- User Impact: Medium

## Context

Track user search queries and provide intelligent autocomplete suggestions. This feature enables:
- **Faster Searching**: Quick access to previous searches without retyping
- **Smart Suggestions**: Autocomplete with relevant past queries
- **History Management**: View and clear search history
- **Improved UX**: Reduce friction in search workflow
- **Analytics Data**: Track popular searches for insights

### User Stories

1. **As a user**, I want to **see suggestions while typing**, so I can **complete searches faster**
2. **As a user**, I want to **view my search history**, so I can **quickly revisit previous searches**
3. **As a user**, I want to **clear my search history**, so I can **remove old or irrelevant searches**
4. **As a user**, I want to **clear individual searches**, so I can **manage my history selectively**
5. **As a user**, I want **frequently searched terms ranked higher**, so I can **find commonly used searches easily**
6. **As a user**, I want **suggestions even when field is empty**, so I can **discover recent searches**

---

## Technical Notes

### Dependencies

**Room Database** for local persistence (may share with other features):
- `androidx.room:room-runtime` (2.6.1+)
- `androidx.room:room-ktx` (2.6.1+)
- `androidx.room:room-compiler` (2.6.1+) - kapt dependency

### Architecture

Following the modular Clean Architecture pattern:

```
domain/searchhistory/
├── model/           ← Search history models
├── repository/      ← Repository interfaces
├── usecase/         ← Business logic
└── di/              ← DI registration

data/searchhistory/
├── local/           ← Room entities & DAOs
├── mapper/          ← Entity mappers
├── repository/      ← Repository implementations
└── di/              ← DI registration

feature/search/
├── SearchScreen.kt  ← Enhanced with suggestions dropdown
├── SearchViewModel  ← Enhanced with suggestions/history
└── SearchModule.kt  ← No changes (DI in domain/data modules)
```

### Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Database** | Room | Local persistence of search history |
| **Coroutines** | Kotlin Coroutines | Async database operations |
| **UI** | Jetpack Compose | Suggestions dropdown |
| **State** | StateFlow & Flow | Reactive suggestions |
| **DI** | Koin | Dependency injection |

---

## Implementation Plan

### Phase 1: Data Layer (Day 1)

Create Room database for search history:

- **Create database entity and DAO** (`data/searchhistory/local/`)
  - Define `SearchHistoryEntity` with: id (auto), query (unique), searchedAt (timestamp), resultCount, sourceTab
  - Create `SearchHistoryDao` with methods for: insert, delete by id, delete by query, clear all, get history
  - Add query methods for suggestions with ranking by frequency and recency
  - Include indexes on query and searchedAt fields for performance

- **Create mappers** (`data/searchhistory/mapper/`)
  - Map between `SearchHistoryEntity` and domain `SearchHistory` model
  - Handle timestamp conversions

### Phase 2: Domain Layer (Day 1)

Define business logic:

- **Create domain layer** (`domain/searchhistory/`)
  - Define `SearchHistory` domain model with id, query, searchedAt, resultCount
  - Create `SearchHistoryRepository` interface with methods for: add, get suggestions, get history, remove item, clear all
  - Create separate use cases: `AddSearchHistoryUseCase`, `GetSearchSuggestionsUseCase`, `GetSearchHistoryUseCase`, `RemoveSearchHistoryItemUseCase`, `ClearSearchHistoryUseCase`

### Phase 3: Feature Layer (Day 2)

Enhance Search screen with suggestions:

- **Update SearchViewModel**
  - Add suggestion-related state: current suggestions list, show suggestions flag, search history list
  - Inject all five use cases
  - Handle query changes: trigger suggestion queries, show/hide history
  - Implement suggestion selection logic: select suggestion, perform search, add to history
  - Handle history management: remove item, clear all

- **Update SearchScreen composable**
  - Add suggestions dropdown below search field
  - Show "Recent Searches" when field is empty
  - Show filtered suggestions when user types
  - Include remove button (✕) on each history item
  - Add "Clear All" button in history section
  - Implement proper dropdown positioning and dismissal

- **Suggestions dropdown UI**
  - Display as dropdown below search field with shadow
  - Show different content based on search field state:
    - Empty: Show recent searches with "Clear All" button
    - Typing: Show filtered suggestions ranked by frequency then recency
  - Allow tap on item to select and search
  - Allow swipe/tap to remove from history

### Phase 4: Dependency Injection & Integration (Day 2)

Set up module registration:

- **Create domain module** with all use case registrations as factories
- **Create data module** with repository singleton registration
- **Update `AppModule`** to include new modules
- **Extend AppDatabase** with search history entity and DAO
- **Update build configuration** for Room compiler

---

## Database Schema

### SearchHistoryEntity Fields

- `id` (Long, auto-increment primary key)
- `query` (String, unique) - the search term
- `searchedAt` (Long) - timestamp of search
- `resultCount` (Int) - number of results returned (optional)
- `sourceTab` (String) - "search" or "trending" context

### Indexes

- Index on `query` field (fast prefix matching)
- Index on `searchedAt` field (fast sorting)
- Unique constraint on `query` to prevent duplicates

---

## Suggestion Ranking

### Algorithm

Rank suggestions by:
1. **Frequency**: How many times the query was searched (COUNT)
2. **Recency**: When it was last searched (ORDER BY searchedAt DESC)

Display top 10-15 suggestions matching the typed prefix.

### Query Optimization

- Use DISTINCT to show each unique query once
- Limit results to prevent large lists
- Index on query for efficient prefix matching
- Index on searchedAt for efficient sorting

---

## UI/UX Details

### Empty State (Field Empty)

Show recent searches section:
- Header: "Recent Searches"
- List: Most recent searches (limit 5-10)
- Each item shows: history icon + query text + remove button
- Footer: "Clear All" button on the right
- Message if no history: "No recent searches"

### Typing State (Field Has Text)

Show suggestions section:
- List: Filtered suggestions matching prefix
- Ranked by: Frequency first, then recency
- Each item shows: suggestion icon + query text
- Limit: Top 10-15 results
- Instant update as user types

### Dropdown Behavior

- Appear below search field with shadow
- Dismiss when: user selects item, field loses focus, user taps outside
- Auto-hide when: user starts typing (might want to show suggestions instead)
- Smooth show/hide animation

---

## Data Persistence

### Storage Strategy

- Persist all search queries indefinitely (or configurable retention)
- Store as local-only (no cloud sync initially)
- Auto-delete when user clears app cache or data

### Privacy

- User has full control: clear individual searches or clear all
- Show transparency: "Search history is stored locally"
- No data sent to servers

---

## Performance Considerations

### Database Optimization

- Indexes on query and searchedAt for fast searches
- DISTINCT query prevents loading duplicates
- LIMIT prevents large result sets
- Flow-based queries for reactive updates

### UI Optimization

- Debounce suggestion queries (wait ~300ms after user stops typing)
- Limit suggestions to 10-15 items max
- Don't load full history at startup
- Cache suggestions in ViewModel temporarily

---

## Error Handling

| Error | Cause | User Impact | Recovery |
|-------|-------|-------------|----------|
| Database Error | Corruption/corruption | Silent - suggestions disabled | Retry or clear history |
| Suggestion Query Fails | DB timeout | Silent - manual input works | Works without suggestions |
| Clear History Fails | DB issue | Show error message | Retry button |

---

## Coding Conventions Alignment

✅ **Clean Architecture**: Separate domain/data layers
✅ **MVVM Pattern**: StateFlow-based suggestions state
✅ **Functional Programming**: Flow operations for queries
✅ **DI Pattern**: Koin modules with proper registration
✅ **Coroutines**: viewModelScope for database operations
✅ **Compose UI**: Stateless dropdown components
✅ **Room Patterns**: Proper DAO and entity design
✅ **Result Pattern**: Safe error handling

---

## Testing Strategy

- Unit tests for each use case
- Unit tests for ViewModel (suggestions, history management)
- Integration tests for repository and DAO queries
- UI tests for suggestions dropdown interaction
- Performance tests for query speed
- Mock database for isolated feature testing

---

## Success Criteria

✅ Suggestions appear while user types
✅ Suggestions ranked by frequency then recency
✅ Search history persists across sessions
✅ Users can clear full history
✅ Users can remove individual searches
✅ History dropdown shows when field is empty
✅ Selecting suggestion performs search
✅ Database queries efficient (< 100ms)
✅ Unit test coverage > 80%
✅ No crashes or memory leaks

---

## Future Enhancements

- 🔍 **Global Trending**: Show trending searches across all users
- 💾 **Search Filters**: Save filter preferences with searches
- 🏷️ **Tags**: Tag searches with custom labels
- 📊 **Statistics**: Show search frequency over time
- 🔔 **Notifications**: Alert when new results for saved searches
- ☁️ **Cloud Sync**: Sync across devices via Firebase
- 🎯 **Smart Suggestions**: ML-based suggestions from behavior
- 🌐 **Community Trends**: Show trending GIF searches
