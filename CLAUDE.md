# ComicVault - Personal Comic Collection Manager

## Project Overview
ComicVault is a web-based application for cataloging and managing personal comic book collections. Users create accounts, bulk-upload their collections via CSV, and access a shared comic database with community-contributed titles. The system supports manual entry, UPC scanning, and internet lookups. An admin dashboard manages users and curates the shared database.

---

## Core Features

### MVP (Phase 1)
1. **User Authentication**
   - Signup/login with email and password
   - Session persistence

2. **Bulk CSV Upload** (primary MVP feature)
   - Users upload CSV file with their collection
   - System parses and validates against schema
   - Maps user's copy data to shared comic database (or creates new entry)
   - Deduplication: if comic already in shared DB, link user's copy; if new, add it
   - Success/error report showing what was imported

3. **Comic Database (Shared)**
   - Auto-populated from user uploads
   - Searchable by title, issue, volume, publisher, creator
   - Displays aggregate data (average price, print info, etc.)

4. **Personal Collection View**
   - Search/filter by any column (title, writer, artist, variant, etc.)
   - View comics owned vs. market data

5. **Admin Dashboard**
   - View/manage all users
   - Manually add/edit comics in shared database
   - View upload history & errors
   - Bulk import CSV (admin-controlled data sources)

### Phase 2+ (Future)
- UPC scanning (camera upload → decode → lookup)
- Internet lookups (ComicVine API, web scraping)
- Real-time notifications when new unique comics added
- Public collection sharing
- Social features (messaging, trading)

---

## Data Schema

### Users Table
```
id (PK)
email (UNIQUE)
password_hash
created_at
updated_at
is_admin (default: false)
```

### Comics Table (Shared Database)
```
id (PK)
upc (NULLABLE, UNIQUE if provided)
publisher
name (title)
volume
number (issue number)
print (printing edition)
cover (cover number/edition)
variant
direct (boolean: direct sale vs. newsstand)
writer
artist
pencils
inker
coverArtist
averagePrice (FLOAT, market value)
printRatio (NULLABLE)
created_at
updated_at
created_by_user_id (FK to Users, tracks who added it)
```

### UserComics Table (User's Personal Copy)
```
id (PK)
user_id (FK)
comic_id (FK)
numberOfBooks (INT, qty of this comic owned)
pricePaid (FLOAT)
pointOfPurchase (VARCHAR)
buyDate (DATE, NULLABLE)
signed (BOOLEAN, default: false)
remarked (BOOLEAN, default: false)
notes (TEXT)
sellDate (DATE, NULLABLE, null = still owned)
created_at
updated_at
```

### CSVImports Table (Audit Trail)
```
id (PK)
user_id (FK)
filename
total_rows
successful_imports
failed_rows
error_log (JSON)
created_at
```

---

## CSV Upload Workflow

### Input Format
User uploads CSV with these columns (exact order doesn't matter, header row required):
```
publisher, name, volume, number, print, cover, variant, direct,
writer, artist, pencils, inker, coverArtist,
numberOfBooks,
pricePaid, pointOfPurchase, buyDate,
averagePrice, printRatio,
signed, remarked,
notes, sellDate
```

### Processing Logic
1. **Validate CSV**: Check headers, data types (dates, floats, booleans, integers)
2. **Deduplicate Entries**: Group by (publisher, name, volume, number, variant, print) to identify potential duplicates within the upload
3. **Match to Shared DB**: 
   - For each row, search Comics table for exact match (publisher, name, volume, number, variant, print)
   - If match found → create UserComics record pointing to existing comic
   - If no match → create new Comics record + UserComics record
4. **Error Handling**: Track validation errors, duplicates, mismatches → return summary to user
5. **Rollback**: If critical errors, either skip those rows or rollback entire upload (TBD with user)

### Response to User
```json
{
  "success": true,
  "total_rows": 50,
  "imported": 48,
  "errors": [
    { "row": 5, "comic": "Spider-Man #1", "error": "Invalid date format" },
    { "row": 12, "comic": "X-Men #101", "error": "Duplicate in upload (row 3)" }
  ],
  "new_comics_added_to_db": 5,
  "existing_comics_linked": 43
}
```

---

## Technical Architecture

### Tech Stack
- **Frontend**: React 18 + TypeScript
  - Tailwind CSS for responsive design (mobile-first)
  - Form handling: React Hook Form
  - File upload: Dropzone.js or native file input
  
- **Backend**: Python 3.11+ with FastAPI
  - Async request handling
  - CSV parsing: pandas or csv module
  - Data validation: Pydantic
  
- **Database**: PostgreSQL 14+
  - Relational structure for comics & users
  - Indexes on frequently searched columns (name, publisher, volume, number)
  
- **Containerization**: Docker + Docker Compose
  - Services: frontend, backend, postgres, redis (optional, for caching)
  
- **Authentication**: JWT tokens (stored in httpOnly cookies)

### Deployment
```yaml
services:
  frontend:
    build: ./frontend
    ports: 3000:3000
    depends_on: [backend]
  
  backend:
    build: ./backend
    ports: 8000:8000
    depends_on: [postgres]
    environment:
      DATABASE_URL: postgresql://...
  
  postgres:
    image: postgres:14
    ports: 5432:5432
    volumes: [postgres_data:/var/lib/postgresql/data]
```

---

## File Structure
```
comicvault/
├── frontend/                 # React app
│   ├── src/
│   │   ├── components/
│   │   │   ├── Auth/
│   │   │   ├── CollectionUpload/
│   │   │   ├── SearchCollection/
│   │   │   └── AdminDashboard/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── App.tsx
│   ├── Dockerfile
│   └── package.json
│
├── backend/                  # FastAPI app
│   ├── app/
│   │   ├── main.py           # App entrypoint
│   │   ├── models.py         # SQLAlchemy ORM models
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── crud.py           # Database operations
│   │   ├── auth.py           # JWT auth
│   │   ├── routes/
│   │   │   ├── users.py
│   │   │   ├── comics.py
│   │   │   ├── uploads.py
│   │   │   └── admin.py
│   │   └── utils/
│   │       └── csv_parser.py # CSV parsing logic
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
│
├── docker-compose.yml
├── .gitignore
└── CLAUDE.md                 # This file
```

---

## MVP Development Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Set up Docker Compose with frontend, backend, postgres
- [ ] Database schema & migrations
- [ ] User auth (signup/login/logout)
- [ ] JWT token management
- [ ] Basic frontend layout (navbar, home, login pages)

### Phase 1.5: CSV Upload (Week 2-3)
- [ ] CSV upload component (React)
- [ ] CSV parser & validator (Python)
- [ ] Deduplication logic
- [ ] Comics database matching algorithm
- [ ] Import error handling & reporting
- [ ] Integration tests

### Phase 2: Collection View (Week 3-4)
- [ ] Search & filter personal collection
- [ ] Display user's comics with all metadata
- [ ] Basic admin dashboard (user management)
- [ ] Manual comic entry (admin)

### Phase 3: Polish & Deploy (Week 4+)
- [ ] Performance optimization (indexes, caching)
- [ ] Error handling & validation improvements
- [ ] UI/UX polish
- [ ] Documentation
- [ ] Docker image optimization

---

## Key Decisions & Rationale

**Data Isolation: Logical Isolation via Foreign Keys**
- All user data lives in one PostgreSQL database
- Each user is completely isolated via `user_id` foreign key relationships
- Users cannot access other users' collections
- Shared Comics table is visible to all users (enables duplicate detection & "new comic" notifications)
- UserComics table is private per user (only they see their personal copies & pricing)
- Backup/restore is simple (one DB per environment)

**Why PostgreSQL?**
- Relational structure is perfect for comics (normalize publisher, creator info)
- Strong ACID guarantees for data consistency
- Supports complex queries (filtering by multiple creators, price ranges, etc.)

**Why FastAPI?**
- Fast, modern Python framework
- Excellent async support for concurrent uploads
- Built-in OpenAPI docs
- Great for data validation with Pydantic

**Why React?**
- Responsive by design, great mobile UX
- Large ecosystem for file uploads, tables, forms
- Easy state management for search/filter

**Bulk CSV as MVP**
- Highest value for personal collection management
- Minimizes manual data entry (solves a pain point)
- Provides foundation for shared comic database
- Can build UPC/internet lookups on top later

**Deduplication Strategy**
- Key: publisher + name + volume + number + variant + print
- This combo should uniquely identify a comic
- Handles reprints, variants, different covers
- UPC (when available) provides additional validation

---

## Notes for Implementation

1. **CSV Parsing**: Use pandas for quick prototyping, switch to csv module if performance needed
2. **Validation**: Validate dates, floats (prices), booleans (signed, remarked) during upload
3. **Null Handling**: Many fields are optional (direct, printRatio, averagePrice, etc.) — allow NULLs
4. **Duplicate Handling in Upload**: If user uploads same comic twice in one CSV, either merge or reject (TBD)
5. **Imageability**: Consider storing comic cover image URLs for future lookups (not MVP)
6. **Search Performance**: Index (publisher, name, volume, number) for fast lookups

---

## Environment Setup
```bash
# Clone repo
git clone ...
cd comicvault

# Create .env files
cp backend/.env.example backend/.env
# Edit backend/.env with DATABASE_URL, JWT_SECRET, etc.

# Spin up
docker-compose up -d

# Create tables
docker-compose exec backend alembic upgrade head

# Seed admin user (optional)
docker-compose exec backend python -c "from app.crud import create_user; create_user(...)"

# Access
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

---

## Future Considerations

- **UPC Scanning**: Integrate pyzbar library, add camera upload component
- **Internet Lookups**: Research ComicVine API, web scraping for comic data
- **Notifications**: WebSockets for real-time "new comic added" broadcasts
- **Analytics**: Track most collected comics, price trends, etc.
- **Mobile App**: React Native or PWA
- **Community Features**: User messaging, trading, ratings/reviews
