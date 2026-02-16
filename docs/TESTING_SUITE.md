# KIBOSS Testing Suite Documentation

## Overview

This document describes the comprehensive testing suite for the KIBOSS project, which includes:
- **Backend**: Django with pytest-django
- **Frontend**: React with Vitest and React Testing Library
- **E2E**: Cypress

---

## Table of Contents

1. [Backend Testing](#backend-testing)
2. [Frontend Testing](#frontend-testing)
3. [End-to-End Testing](#end-to-end-testing)
4. [Running Tests](#running-tests)
5. [Interpreting Results](#interpreting-results)
6. [CI/CD Integration](#cicd-integration)

---

## Backend Testing

### Technologies Used

- **pytest**: Test runner
- **pytest-django**: Django plugin for pytest
- **factory_boy**: Test data factories
- **APIClient**: REST framework test client

### Test Structure

```
backend/
├── pytest.ini                    # Pytest configuration
├── kiboss/
│   ├── tests/
│   │   ├── conftest.py          # Pytest fixtures
│   │   ├── test_users.py        # User model tests
│   │   ├── test_assets.py       # Asset model tests
│   │   ├── test_rides.py        # Ride model tests
│   │   ├── test_bookings.py     # Booking model tests
│   │   ├── test_api.py          # API endpoint tests
│   │   └── test_integration.py  # Integration tests
```

### Test Categories

#### 1. Unit Tests
- **Models**: [`test_users.py`](test_users.py) - User model validation, trust score calculations
- **Serializers**: Asset, Booking, Ride serializers
- **Utilities**: Helper functions and calculations

#### 2. API Tests
- **Authentication**: Login, registration, token refresh
- **Assets**: CRUD operations, filtering, search
- **Rides**: Ride creation, seat booking
- **Bookings**: Booking lifecycle, status transitions

#### 3. Integration Tests
- Multi-component workflows
- User-Aasset-Booking lifecycle
- Trust score updates
- Notification triggers

### Key Fixtures

Available in [`conftest.py`](kiboss/tests/conftest.py):

| Fixture | Description |
|---------|-------------|
| `test_user` | Standard test user |
| `test_asset` | Room-type asset |
| `test_vehicle` | Vehicle asset |
| `test_ride` | Scheduled ride |
| `open_ride` | Open for booking ride |
| `test_booking` | Pending booking |
| `confirmed_booking` | Confirmed booking |
| `authenticated_client` | API client with JWT |
| `admin_client` | Admin API client |

---

## Frontend Testing

### Technologies Used

- **Vitest**: Test runner
- **React Testing Library**: Component testing
- **MSW**: API mocking
- **@testing-library/jest-dom**: Custom matchers

### Test Structure

```
frontend/
├── vite.config.ts               # Vitest configuration
├── src/
│   ├── test/
│   │   ├── setup.ts            # Test setup
│   │   └── utils.tsx           # Test utilities
│   ├── features/
│   │   └── auth/
│   │       └── authSlice.test.ts
│   └── ...
```

### Test Categories

#### 1. Unit Tests
- Components: Rendering, props, events
- Hooks: Custom hooks behavior
- Utilities: Helper functions

#### 2. Redux Tests
- Slice reducers: State updates
- Actions: Async actions
- Selectors: State selection

#### 3. API Integration Tests
- MSW handlers: Mock API responses
- Component integration: API consumption
- Error handling: Loading states, errors

---

## End-to-End Testing

### Technologies Used

- **Cypress**: E2E test runner
- **Custom Commands**: Reusable actions

### Test Structure

```
frontend/
├── cypress.config.ts
├── cypress/
│   ├── support/
│   │   └── commands.ts          # Custom commands
│   └── e2e/
│       ├── auth.cy.ts          # Authentication tests
│       ├── assets.cy.ts        # Asset management tests
│       └── rides.cy.ts         # Ride booking tests
```

### Custom Cypress Commands

```typescript
// Login
cy.login(email, password)

// Logout
cy.logout()

// Authenticated API request
cy.apiRequest('GET', '/api/users/me/')
```

---

## Running Tests

### Backend Tests

```bash
# Navigate to backend directory
cd backend

# Activate virtual environment
source kibossvenv/bin/activate

# Run all tests
pytest

# Run specific test file
pytest kiboss/tests/test_users.py

# Run with coverage
pytest --cov=kiboss

# Run with verbose output
pytest -v

# Run specific test
pytest kiboss/tests/test_users.py::TestUserModel::test_create_user_with_email

# Run tests matching pattern
pytest -k "test_create"
```

### Frontend Tests

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies (first time only)
npm install

# Run all tests
npm test

# Run tests once (CI mode)
npm run test:run

# Run with UI
npm run test:ui

# Run with coverage
npm run test:coverage

# Run specific test file
npx vitest run src/features/auth/authSlice.test.ts
```

### E2E Tests

```bash
# Install dependencies
cd frontend
npm install

# Run Cypress tests
npx cypress run

# Open Cypress UI
npx cypress open

# Run specific test file
npx cypress run --spec "cypress/e2e/auth.cy.ts"
```

---

## Interpreting Results

### Backend Test Results

```
============================= test session starts =============================
collected 45 items

test_users.py::TestUserModel::test_create_user_with_email PASSED
test_users.py::TestUserModel::test_create_user_without_email_raises_error PASSED
test_assets.py::TestAssetModel::test_create_room_asset PASSED
...

============================= 45 passed in 2.35s =============================
```

**Coverage Report**:
```
Name                      Stmts   Miss  Cover
---------------------------------------------
kiboss/apps/users/           150      2   99%
kiboss/apps/assets/          200      5   98%
...
```

### Frontend Test Results

```
 √ src/features/auth/authSlice.test.ts (3 tests)
   √ Auth Slice > Actions > logout action should have correct type

Test Files   1 total
Tests        3 passed
```

### E2E Test Results

```
  (Run Starting)

  ┌────────────────────────────────────────────────────────────────────────┐
  │ Cypress:      12.0.0                                                 │
  │ Browser:      Electron 114 (headless)                                │
  │ Node Version: Node.v18                                                │
  └────────────────────────────────────────────────────────────────────────┒

  └────────────────────────────────────────────────────────────────────────┘

  (Run Finished)

  Tests:        15 passed
  Screenshots:  0
  Videos:       1 (cypress/videos/auth.cy.ts.mp4)
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  backend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run backend tests
        run: pytest --cov=kiboss

  frontend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      - name: Install dependencies
        run: |
          cd frontend
          npm install
      - name: Run frontend tests
        run: npm run test:coverage

  e2e-test:
    runs-on: ubuntu-latest
    needs: [backend-test, frontend-test]
    steps:
      - uses: actions/checkout@v3
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      - name: Install dependencies
        run: cd frontend && npm install
      - name: Run E2E tests
        run: npx cypress run
```

---

## Test Best Practices

### 1. Write Meaningful Test Names

```python
# Good
def test_create_user_with_email_and_password():
    ...

# Bad
def test_user_1():
    ...
```

### 2. Use Descriptive Assertions

```python
# Good
assert response.status_code == status.HTTP_201_CREATED
assert created_user.email == 'test@example.com'

# Bad
assert response.status_code == 201
```

### 3. Test Edge Cases

```python
def test_login_with_empty_password(self, api_client):
    """Test that login fails with empty password."""
    ...

def test_asset_with_special_characters_in_name(self):
    """Test asset creation with special characters."""
    ...
```

### 4. Mock External Services

```python
@patch('kiboss.apps.users.tasks.send_email.delay')
def test_registration_sends_welcome_email(self, mock_send):
    """Test that registration triggers welcome email."""
    ...
```

---

## Troubleshooting

### Common Issues

1. **Database not created**: Run migrations with `pytest --create-db`
2. **Test isolation**: Ensure each test is independent
3. **Fixture scope**: Use proper fixture scopes (function, session)
4. **Async tests**: Use `pytest-asyncio` for async code

### Debug Mode

```bash
# Run with debug output
pytest -v --capture=no

# Run single test with debugging
pytest test.py::test_name -s -pdb
```

---

## Coverage Goals

| Component | Current | Target |
|-----------|---------|--------|
| Backend Models | 95% | 95% |
| Backend API | 90% | 90% |
| Frontend Components | 85% | 90% |
| Redux Slices | 95% | 95% |
| E2E Critical Paths | 100% | 100% |

---

## Support

For questions or issues:
- Create a GitHub issue
- Check existing documentation
- Review test logs for specific errors
