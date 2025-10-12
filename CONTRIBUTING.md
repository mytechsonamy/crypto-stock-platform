# Contributing to Crypto-Stock Platform

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Coding Standards](#coding-standards)
- [Documentation](#documentation)

## 📜 Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Maintain professional communication

## 🚀 Getting Started

1. **Fork the repository**
2. **Clone your fork**
   ```bash
   git clone https://github.com/your-username/crypto-stock-platform.git
   cd crypto-stock-platform
   ```
3. **Add upstream remote**
   ```bash
   git remote add upstream https://github.com/original/crypto-stock-platform.git
   ```

## 🛠️ Development Setup

### Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Start services
docker-compose up -d timescaledb redis
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## 🔨 Making Changes

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test additions/changes

### 2. Make Your Changes

- Write clean, readable code
- Follow existing code style
- Add comments for complex logic
- Update documentation as needed

### 3. Test Your Changes

```bash
# Backend tests
pytest tests/

# Frontend tests
cd frontend && npm test

# Linting
black .
flake8 .
mypy .
```

## 🧪 Testing

### Writing Tests

- Write tests for new features
- Maintain test coverage above 80%
- Use descriptive test names
- Test edge cases

### Test Structure

```python
# tests/unit/test_feature.py
import pytest

def test_feature_basic_functionality():
    """Test basic functionality of feature"""
    # Arrange
    input_data = {...}
    
    # Act
    result = feature_function(input_data)
    
    # Assert
    assert result == expected_output
```

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_circuit_breaker.py

# With coverage
pytest --cov=. --cov-report=html

# Integration tests
pytest tests/integration/
```

## 📤 Submitting Changes

### 1. Commit Your Changes

```bash
git add .
git commit -m "feat: add new feature"
```

Commit message format:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `style:` - Formatting
- `refactor:` - Code restructuring
- `test:` - Tests
- `chore:` - Maintenance

### 2. Push to Your Fork

```bash
git push origin feature/your-feature-name
```

### 3. Create Pull Request

- Go to GitHub repository
- Click "New Pull Request"
- Select your branch
- Fill in PR template
- Request review

### Pull Request Checklist

- [ ] Tests pass
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Commit messages are clear
- [ ] No merge conflicts
- [ ] PR description is complete

## 📝 Coding Standards

### Python (Backend)

- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use docstrings for functions/classes
- Format with Black
- Lint with Flake8
- Type check with MyPy

Example:
```python
from typing import List, Optional

def process_data(
    data: List[dict],
    filter_value: Optional[str] = None
) -> List[dict]:
    """
    Process data with optional filtering.
    
    Args:
        data: List of data dictionaries
        filter_value: Optional filter value
        
    Returns:
        Processed data list
    """
    # Implementation
    pass
```

### TypeScript (Frontend)

- Use TypeScript strict mode
- Define interfaces for data structures
- Use functional components
- Follow React best practices
- Format with Prettier
- Lint with ESLint

Example:
```typescript
interface ChartData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export const ChartComponent: React.FC<Props> = ({ data }) => {
  // Implementation
};
```

### General Guidelines

- **DRY**: Don't Repeat Yourself
- **KISS**: Keep It Simple, Stupid
- **YAGNI**: You Aren't Gonna Need It
- **Single Responsibility**: One function, one purpose
- **Meaningful Names**: Use descriptive variable/function names

## 📚 Documentation

### Code Documentation

- Add docstrings to all public functions/classes
- Include parameter descriptions
- Document return values
- Add usage examples for complex functions

### README Updates

- Update README.md for new features
- Add configuration examples
- Update architecture diagrams if needed

### API Documentation

- Document new API endpoints
- Include request/response examples
- Update OpenAPI/Swagger specs

## 🐛 Reporting Bugs

### Bug Report Template

```markdown
**Description**
Clear description of the bug

**Steps to Reproduce**
1. Step 1
2. Step 2
3. Step 3

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.11]
- Docker: [e.g., 24.0.0]

**Logs**
```
Relevant log output
```

**Screenshots**
If applicable
```

## 💡 Feature Requests

### Feature Request Template

```markdown
**Feature Description**
Clear description of the feature

**Use Case**
Why is this feature needed?

**Proposed Solution**
How should it work?

**Alternatives Considered**
Other approaches you've thought about

**Additional Context**
Any other relevant information
```

## 🔍 Code Review Process

### For Reviewers

- Be constructive and respectful
- Explain reasoning for suggestions
- Approve when ready
- Request changes if needed

### For Contributors

- Respond to feedback promptly
- Ask questions if unclear
- Make requested changes
- Re-request review after updates

## 📊 Performance Guidelines

- Optimize database queries
- Use caching appropriately
- Avoid N+1 queries
- Profile before optimizing
- Document performance considerations

## 🔒 Security Guidelines

- Never commit secrets
- Use environment variables
- Validate all inputs
- Sanitize user data
- Follow OWASP guidelines

## 📞 Getting Help

- Check existing issues
- Read documentation
- Ask in discussions
- Contact maintainers

## 🎯 Priority Labels

- `critical` - Security issues, data loss
- `high` - Major bugs, important features
- `medium` - Minor bugs, enhancements
- `low` - Nice-to-have features

## 🏆 Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Credited in documentation

## 📅 Release Process

1. Version bump
2. Update CHANGELOG
3. Create release branch
4. Run full test suite
5. Deploy to staging
6. Final review
7. Merge to main
8. Tag release
9. Deploy to production

## 🙏 Thank You!

Your contributions make this project better for everyone. We appreciate your time and effort!

---

**Questions?** Open an issue or contact the maintainers.
