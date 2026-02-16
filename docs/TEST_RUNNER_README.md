# KIBOSS Integration Tests - Database to UI Verification

This document describes how to run integration tests that verify data created in the Django database is correctly rendered in the frontend UI.

## Overview

The integration tests:
1. **Create data via Django ORM** - Using Django's TestCase
2. **Query API endpoints** - Verify data is accessible via REST API
3. **Load frontend pages** - Using Cypress to navigate the UI
4. **Assert data matches** - Verify DB records equal UI renderings
5. **FAIL if mismatch** - Tests explicitly fail if DB data isn't visible in UI

## Test Files

### Backend Integration Tests
- [`test_integration_e2e.py`](kiboss/tests/test_integration_e2e.py) - Django TestCase that creates real database records

### Frontend Integration Tests
- [`integration-database.cy.ts`](frontend/cypress/e2e/integration-database.cy.ts) - Cypress E2E tests that verify UI renders DB data

## Running Backend Integration Tests

### Setup

1. Ensure Django is configured:
```bash
cd backend
source kibossvenv/bin/activate
pip install -r requirements.txt
```

2. Run the integration tests:
```bash
cd backend
python manage.py test kiboss.tests.test_integration_e2e -v 2
```

### What the Tests Verify

```python
# Test 1: Data created in DB exists
def test_assets_created_in_db(self):
    assets = Asset.objects.filter(name__icontains='Integration Test')
    self.assertEqual(assets.count(), 2)

# Test 2: API returns correct data
def test_assets_api_returns_correct_data(self):
    response = self.client.get('/api/v1/assets/')
    self.assertIn('Integration Test Apartment', asset_names)

# Test 3: Relationships are correct
def test_asset_owner_relationship(self):
    asset = Asset.objects.get(name='Integration Test Apartment')
    self.assertEqual(asset.owner.email, 'owner_integration@test.com')
```

## Running Frontend Database-to-UI Tests

### Prerequisites

1. **Django test server running** on port 8000
2. **Frontend dev server running** on port 5173

### Setup Steps

1. **Start Django server**:
```bash
cd backend
source kibossvenv/bin/activate
python manage.py runserver 8000
```

2. **In another terminal, start frontend**:
```bash
cd frontend
npm run dev
```

3. **Install Cypress** (first time only):
```bash
cd frontend
npm install
npx cypress install
```

4. **Run the integration tests**:
```bash
cd frontend
DJANGO_API_URL=http://localhost:8000/api/v1 npx cypress run --spec "cypress/e2e/integration-database.cy.ts"
```

### What the Tests Verify

```typescript
// Test: DB record count equals UI rendered count
it('FAIL if DB has booking but UI shows empty', () => {
  // Get bookings from DB
  cy.request(`${API_URL}/bookings/`).then((response) => {
    const dbBookingCount = response.body.count
    
    // This FAILS if DB has data but UI is empty
    if (dbBookingCount > 0) {
      cy.get('[data-testid="booking-card"]')
        .should('exist')
        .and('have.length.at.least', dbBookingCount)
    }
  })
})

// Test: Asset details match exactly
it('should verify asset details match database', () => {
  // Get asset from DB
  cy.request(`${API_URL}/assets/`).then((response) => {
    const testAsset = response.body.results[0]
    
    // Verify each field matches
    cy.visit(`/assets/${testAsset.id}`)
    cy.contains(testAsset.name).should('be.visible')
    cy.contains(testAsset.description).should('be.visible')
    cy.contains(testAsset.city).should('be.visible')
  })
})
```

## Automated Test Runner Script

Create `run_integration_tests.sh`:

```bash
#!/bin/bash

echo "=== KIBOSS Integration Tests ==="

# Kill any existing servers
pkill -f "python manage.py runserver" || true
pkill -f "npm run dev" || true

# Setup backend
echo "Setting up backend..."
cd backend
source kibossvenv/bin/activate
pip install -r requirements.txt > /dev/null 2>&1

# Run backend tests
echo "Running backend integration tests..."
python manage.py test kiboss.tests.test_integration_e2e -v 2

if [ $? -ne 0 ]; then
  echo "Backend tests FAILED"
  exit 1
fi

echo "Backend tests PASSED"

# Start Django server in background
echo "Starting Django server..."
python manage.py runserver 8000 > /tmp/django.log 2>&1 &
DJANGO_PID=$!
sleep 3

# Start frontend
echo "Starting frontend server..."
cd ../frontend
npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
sleep 5

# Run Cypress tests
echo "Running Cypress database-to-UI tests..."
DJANGO_API_URL=http://localhost:8000/api/v1 npx cypress run --spec "cypress/e2e/integration-database.cy.ts"

CYPRESS_EXIT=$?

# Cleanup
echo "Cleaning up..."
kill $DJANGO_PID $FRONTEND_PID || true

if [ $CYPRESS_EXIT -ne 0 ]; then
  echo "Cypress tests FAILED"
  exit 1
fi

echo "=== All Integration Tests PASSED ==="
```

## CI/CD Pipeline Integration

Add to your `.github/workflows/integration-tests.yml`:

```yaml
name: Integration Tests

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    
    services:
      redis:
        image: redis
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install backend dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      
      - name: Run Django migrations
        run: |
          cd backend
          python manage.py migrate
      
      - name: Run backend integration tests
        run: |
          cd backend
          python manage.py test kiboss.tests.test_integration_e2e -v 2
      
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install frontend dependencies
        run: |
          cd frontend
          npm install
      
      - name: Start Django server
        run: |
          cd backend
          python manage.py runserver 8000 &
          sleep 5
      
      - name: Start frontend server
        run: |
          cd frontend
          npm run dev &
          sleep 5
      
      - name: Run Cypress integration tests
        run: |
          cd frontend
          DJANGO_API_URL=http://localhost:8000/api/v1 npx cypress run --spec "cypress/e2e/integration-database.cy.ts"
```

## Test Assertions Reference

### Backend Assertions

| Assertion | Description |
|-----------|-------------|
| `self.assertEqual(count, 2)` | Exact count match |
| `self.assertIn(name, list)` | Contains expected value |
| `self.assertEqual(asset.owner.email, '...')` | Relationship verification |
| `self.assertGreater(count, 0)` | Non-empty results |

### Frontend Assertions

| Assertion | Description |
|-----------|-------------|
| `cy.get('[data-testid="card"]').should('have.length', n)` | Count match |
| `cy.contains('text').should('be.visible')` | Text rendering |
| `cy.get('[data-testid="count"]').should('contain', n)` | Displayed count |
| `.should('exist')` | Element exists |

## Troubleshooting

### Port Already in Use
```bash
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9
```

### Cypress Not Found
```bash
cd frontend
npm install
npx cypress install
```

### Database Not Resetting
```bash
cd backend
rm -f db.sqlite3
python manage.py migrate
python manage.py test kiboss.tests.test_integration_e2e
```

### API Returns 404
- Verify Django server is running on correct port
- Check API URL matches `http://localhost:8000/api/v1`
- Ensure CORS is enabled in Django settings

## Expected Test Output

### Backend Tests
```
System check identified no issues (0 silenced).
test_assets_created_in_db (kiboss.tests.test_integration_e2e.IntegrationTestCase) ... ok
test_assets_api_returns_correct_data (kiboss.tests.test_integration_e2e.IntegrationTestCase) ... ok
test_rides_created_in_db (kiboss.tests.test_integration_e2e.IntegrationTestCase) ... ok
test_bookings_created_in_db (kiboss.tests.test_integration_e2e.IntegrationTestCase) ... ok
...
Ran 10 tests in 2.345s
OK
```

### Cypress Tests
```
  (Database to UI Integration Tests)

    ✓ should display all assets from database in the assets list
    ✓ should show exact asset name from database  
    ✓ should display correct asset count
    ✓ should verify asset details match database
    ...

  15 passing (23.4s)
```

## Fail Scenarios

These tests **explicitly FAIL** when:

1. **Data exists in DB but not in UI**
   ```typescript
   if (dbBookingCount > 0) {
     cy.get('[data-testid="booking-card"]').should('exist')
   }
   ```

2. **Counts don't match**
   ```typescript
   expect(uiCount).to.be.greaterThanOrEqual(dbCount)
   ```

3. **Field values differ**
   ```typescript
   cy.contains(testAsset.name).should('be.visible')
   ```

4. **Relationships broken**
   ```python
   self.assertEqual(asset.owner.email, expected_email)
   ```
