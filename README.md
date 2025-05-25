# Global Classifier

## Setup and Installation
This project is setup using the `uv` package manager. To run the project, you have to install `uv` and then run the below commands.

```bash
uv venv
uv sync
```

Before installing any package you need to make sure to activate the environment, you can do this by running

Mac OS / Linux:
```bash
source .venv/bin/activate
``` 

Windows:

```bash
.venv/Scripts/activate
``` 


## Contributing

This section outlines the guidelines for contributing to the Global Classifier project. Please read through these before submitting any changes.

### Folder Structure

The project is organized into several key directories to maintain clarity and modularity:

*   `configs/`: Holds global configuration files essential for different parts of the project.
*   `docs/`: Contains all project documentation, including architectural diagrams (e.g., `classifier-architecture.drawio`), setup guides, technical explanations, and usage manuals.
*   `DSL/`: Contains components related to DSLs belonging different to BYK stack services.
*   `GUI/`: Contains the source code, assets, and build configurations for the project's Graphical User Interface. 
*   `local-classifier/`: A copy of the local-classifier repo for module re-use purposes. Will be discarded after initial release
*   `src/`: Contains the core source code for the Global Classifier. This is further divided into modules for specific functionalities like:
    *   `dataset-generation/`: Scripts and tools for creating and preparing datasets.
    *   `inference/`: Code related to running model predictions.
    *   `model-training/`: Scripts and notebooks for training machine learning models.
    *   `tests/`: Unit, integration, or end-to-end tests for the `src/` components.

Understanding this structure will help you locate relevant files and understand the project's architecture.

### Linting with Ruff

We use **Ruff** for linting Python code to ensure consistency and catch potential errors early. Ruff is an extremely fast Python linter and formatter, written in Rust.

**How Ruff Works (Example):**

Consider the following Python code snippet which has a few style issues:

```python
import os,sys # Multiple imports on one line

def process_data(data, unused_param): # Unused function parameter
    print ("Processing") # Print statement with extra space
    if data is not None:
        return True
    else:
        return False
```

When you run Ruff on this code (e.g., `ruff check .` or `ruff format . --check`), it will flag these issues:

*   An error for multiple imports on one line (`import os,sys`). Ruff would suggest `import os; import sys` or separate lines.
*   An error for the `unused_param` not being used within the `process_data` function.
*   Formatting issues might also be flagged if `ruff format` is used or its rules are enabled in `ruff check`.

All Python contributions must be free of Ruff linting errors. You can check your code by running `ruff check .` and `ruff format .` in the relevant directory.

### Package Management with uv

This project uses **uv** as the primary package manager for Python dependencies. `uv` is a fast Python package installer and resolver, designed as a drop-in replacement for `pip` and `pip-tools`.

You will typically use `uv` to manage virtual environments and install dependencies listed in `requirements.txt` files found within various modules (especially in the `local-classifier/` subdirectories and `src/`).

Example command to create a virtual environment and install dependencies for a module:
```bash
uv venv # Create a virtual environment in .venv
uv pip install -r requirements.txt # Install dependencies
```
Ensure your development environment is set up using `uv` for consistency.
If suppose you have already created your environment using any other framework like `conda` or `venv`, then simply create a new `uv` project and copy your existing code into the project while making sure no path references are broken.



### Build Process and Code Quality

To maintain a high standard of code quality and ensure project stability, the following practices are enforced:

*   **Ruff Linting is Mandatory:** All submitted Python code must pass Ruff linting checks.
*   **Build Success:** Automated builds (e.g., via GitHub Actions) will only succeed if all checks, including Ruff linting, pass. Pull requests with failing checks will not be merged.

Please run Ruff locally to check your code before pushing changes or creating a pull request. This helps streamline the review process and maintain a clean codebase.



## Branch Management Strategy

The project follows a three-tier branching workflow to streamline development, testing, and integration.

### Branch Definitions

- **wip (work in progress)**: Primary branch for ongoing work. All new features and fixes are merged here first.  
- **testing**: Integration branch where code from **WIP** is validated by automated tests and QA.  
- **dev**: Development-ready branch. Code that passes testing is merged here for further staging or release processes.

### Contribution Process

1. Fork the repository and clone it locally.  
2. Create a new feature/fix branch based off `wip`.  
3. Make your changes, run Ruff linting and formatting, commit your changes, and ensure all checks pass.
4. Push your branch to the remote and open a Pull Request targeting `wip`.  
5. After review approval, maintainers merge your changes into `testing`.  
6. Automated tests and QA are executed on `testing`.  
7. Once testing is successful, maintainers merge `testing` into `dev`.  
8. From `dev`, code may proceed through further release pipelines or staging environments.

## Testing Requirements

#### Python Unit Testing

All Python modules in this project require comprehensive unit tests. Follow these guidelines when writing tests:

1. **Test Framework**: Use `pytest` for all Python unit tests.
2. **Test Location**: Place tests in the `src/tests/` directory, mirroring the structure of the module being tested.
3. **Naming Convention**: Name test files with the `test_` prefix (e.g., `test_classifier.py`).
4. **Coverage**: Aim for at least 80% code coverage for all modules.
5. **Test Isolation**: Each test should be independent and not rely on the state of other tests.

Example of a well-structured test:

```python
import pytest
from src.inference.classifier import classify_text

def test_classify_text_empty_input():
    """Test classification behavior with empty input."""
    result = classify_text("")
    assert result == "unknown"

def test_classify_text_valid_input():
    """Test classification with valid sample text."""
    sample = "This is a sample technical query about databases."
    result = classify_text(sample)
    assert result in ["database", "technical"]
```

#### Frontend Testing with Playwright

All frontend components in the GUI directory require automated tests using Playwright:

1. **Test Directory**: Place Playwright tests in `GUI/tests/`.
2. **Coverage Requirements**: Tests must cover:
   - All critical user flows
   - Component rendering
   - State management
   - Error handling scenarios

3. **Multi-browser Testing**: Tests should run against at least two majors browsers (Chrome and Firefox).

Example Playwright test structure:

```typescript
import { test, expect } from '@playwright/test';

test.describe('Classifier UI', () => {
  test('should display classification results correctly', async ({ page }) => {
    await page.goto('/classifier');
    await page.fill('#input-text', 'Sample query about Azure services');
    await page.click('#classify-button');
    
    // Check if results appear
    const results = await page.locator('.classification-results');
    await expect(results).toBeVisible();
    
    // Verify correct classification appears
    const category = await page.locator('.category-label').textContent();
    expect(['cloud', 'azure']).toContain(category);
  });
});
```

All tests must pass before PR approval and merge into the `wip` branch.
