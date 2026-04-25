# ============================================================================
# Git Aliases for LEAN Algorithm Development
# ============================================================================
#
# This file contains git aliases that support Conventional Commits workflow
# for branch management, commit formatting, version control operations,
# and project-specific shortcuts for LEAN algo trading strategies.
#
# INSTALLATION:
#   Option 1 (project-only): Run from repo root:
#       git config --local include.path ../git_aliases.sh
#
#   Option 2 (manual): Copy the [alias] section below into .git/config
#
#   Option 3 (global): Copy into ~/.gitconfig (applies to all repos)
#
# VERIFY:
#       git config --get-regexp alias
#
# CONVENTIONAL COMMITS OVERVIEW:
#   Commit format: <type>[scope]: <description>
#   Types: feat, fix, test, docs, refactor, chore, perf, ci, style
#   Scopes: handlers, universe, config, main, tests, data, docs, rag
#
# STRATEGY-SPECIFIC SCOPES (add your own):
#   handlers       — Pure Python handler modules (business logic)
#   universe       — universe_filter.py (symbol selection)
#   config         — config.py, pyproject.toml
#   main           — main.py (LEAN entry point / orchestration)
#   tests          — tests/ directory (unit, integration)
#   data           — data_handler.py (market data + indicators)
#   docs           — docs/ directory
#   rag            — rag/ pipeline (crawler, processing, storage)
#   adapters       — adapters/ (platform portability)
#
# ============================================================================

[alias]
    # ========================================================================
    # BRANCH MANAGEMENT
    # ========================================================================

    # Create and switch to a new branch with Conventional Commits prefix
    # Usage: git new-branch <type> <description> [base-branch]
    # Example: git new-branch feat add-rsi-filter main
    # Creates: feat/add-rsi-filter from main (defaults to main if omitted)
    #
    # Supported types: feat, fix, test, docs, refactor, chore, perf, ci
    new-branch = "!f() { \
        if [ -z \"$1\" ] || [ -z \"$2\" ]; then \
            echo \"Usage: git new-branch <type> <description> [base-branch]\"; \
            echo \"Example: git new-branch feat add-rsi-filter main\"; \
            echo \"Types: feat, fix, test, docs, refactor, chore, perf, ci\"; \
            return 1; \
        fi; \
        base=${3:-main}; \
        git checkout -b \"$1/$2\" \"$base\"; \
    }; f"

    # Push changes and set upstream branch in one command
    # Usage: git push-up
    push-up = "!f() { \
        branch=$(git branch --show-current); \
        echo \"Pushing $branch to origin and setting upstream...\"; \
        git push --set-upstream origin \"$branch\"; \
    }; f"

    # Sync current branch with main (fetch + rebase)
    # Usage: git sync-main
    sync-main = "!f() { \
        branch=$(git branch --show-current); \
        echo \"Syncing $branch with origin/main...\"; \
        git fetch origin main && \
        git rebase origin/main; \
    }; f"

    # Merge a branch into the base branch
    # Usage: git merge-to-base <base-branch> <feature-branch>
    # Example: git merge-to-base main feat/add-rsi-filter
    merge-to-base = "!f() { \
        if [ -z \"$1\" ] || [ -z \"$2\" ]; then \
            echo \"Usage: git merge-to-base <base-branch> <feature-branch>\"; \
            return 1; \
        fi; \
        git checkout \"$1\" && git merge \"$2\"; \
    }; f"

    # Delete a branch locally and remotely
    # Usage: git delete-branch <branch-name>
    # Example: git delete-branch feat/add-rsi-filter
    delete-branch = "!f() { \
        if [ -z \"$1\" ]; then \
            echo \"Usage: git delete-branch <branch-name>\"; \
            return 1; \
        fi; \
        echo \"Deleting branch $1 locally and remotely...\"; \
        git branch -d \"$1\" && \
        git push origin --delete \"$1\" 2>/dev/null || echo \"Remote branch already deleted or doesn't exist\"; \
    }; f"

    # ========================================================================
    # CONVENTIONAL COMMITS HELPERS
    # ========================================================================

    # Commit with 'feat' type (new feature)
    # Usage: git commit-feat "<scope>" "<description>"
    # Example: git commit-feat "handlers" "add RSI filter to technical validator"
    commit-feat = "!f() { \
        if [ -z \"$2\" ]; then \
            echo \"Usage: git commit-feat '<scope>' '<description>'\"; \
            echo \"Scopes: handlers, universe, config, main, tests, data, docs, rag, adapters\"; \
            return 1; \
        fi; \
        git commit -m \"feat($1): $2\"; \
    }; f"

    # Commit with 'fix' type (bug fix)
    # Usage: git commit-fix "<scope>" "<description>"
    # Example: git commit-fix "handlers" "correct stop-loss exit logic"
    commit-fix = "!f() { \
        if [ -z \"$2\" ]; then \
            echo \"Usage: git commit-fix '<scope>' '<description>'\"; \
            echo \"Scopes: handlers, universe, config, main, tests, data, docs, rag, adapters\"; \
            return 1; \
        fi; \
        git commit -m \"fix($1): $2\"; \
    }; f"

    # Commit with 'test' type (test additions/changes)
    # Usage: git commit-test "<scope>" "<description>"
    # Example: git commit-test "handlers" "add position manager unit tests"
    commit-test = "!f() { \
        if [ -z \"$2\" ]; then \
            echo \"Usage: git commit-test '<scope>' '<description>'\"; \
            echo \"Scopes: handlers, universe, config, main, tests, data, docs, rag, adapters\"; \
            return 1; \
        fi; \
        git commit -m \"test($1): $2\"; \
    }; f"

    # Commit with 'docs' type (documentation)
    # Usage: git commit-docs "<scope>" "<description>"
    # Example: git commit-docs "readme" "update architecture overview"
    commit-docs = "!f() { \
        if [ -z \"$2\" ]; then \
            echo \"Usage: git commit-docs '<scope>' '<description>'\"; \
            return 1; \
        fi; \
        git commit -m \"docs($1): $2\"; \
    }; f"

    # Commit with 'refactor' type (code restructuring)
    # Usage: git commit-refactor "<scope>" "<description>"
    # Example: git commit-refactor "handlers" "extract shared indicator logic"
    commit-refactor = "!f() { \
        if [ -z \"$2\" ]; then \
            echo \"Usage: git commit-refactor '<scope>' '<description>'\"; \
            return 1; \
        fi; \
        git commit -m \"refactor($1): $2\"; \
    }; f"

    # Commit with 'chore' type (maintenance)
    # Usage: git commit-chore "<scope>" "<description>"
    # Example: git commit-chore "deps" "update pytest to 9.x"
    commit-chore = "!f() { \
        if [ -z \"$2\" ]; then \
            echo \"Usage: git commit-chore '<scope>' '<description>'\"; \
            return 1; \
        fi; \
        git commit -m \"chore($1): $2\"; \
    }; f"

    # Commit with 'perf' type (performance improvement)
    # Usage: git commit-perf "<scope>" "<description>"
    # Example: git commit-perf "data" "cache indicator calculations"
    commit-perf = "!f() { \
        if [ -z \"$2\" ]; then \
            echo \"Usage: git commit-perf '<scope>' '<description>'\"; \
            return 1; \
        fi; \
        git commit -m \"perf($1): $2\"; \
    }; f"

    # Commit with 'ci' type (CI/CD changes)
    # Usage: git commit-ci "<scope>" "<description>"
    # Example: git commit-ci "github" "add test workflow"
    commit-ci = "!f() { \
        if [ -z \"$2\" ]; then \
            echo \"Usage: git commit-ci '<scope>' '<description>'\"; \
            return 1; \
        fi; \
        git commit -m \"ci($1): $2\"; \
    }; f"

    # Commit with breaking change indicator
    # Usage: git commit-breaking "<type>" "<scope>" "<description>"
    # Example: git commit-breaking "feat" "config" "restructure position sizing params"
    commit-breaking = "!f() { \
        if [ -z \"$3\" ]; then \
            echo \"Usage: git commit-breaking '<type>' '<scope>' '<description>'\"; \
            echo \"Example: git commit-breaking 'feat' 'config' 'restructure params'\"; \
            return 1; \
        fi; \
        git commit -m \"$1($2)!: $3\"; \
    }; f"

    # ========================================================================
    # COMMIT MESSAGE UTILITIES
    # ========================================================================

    # Amend last commit message
    # Usage: git commit-amend-msg "<new-message>"
    # Example: git commit-amend-msg "fix(handlers): correct stop-loss comparison"
    commit-amend-msg = "!f() { \
        if [ -z \"$1\" ]; then \
            echo \"Usage: git commit-amend-msg '<new-message>'\"; \
            return 1; \
        fi; \
        git commit --amend -m \"$1\"; \
    }; f"

    # Open editor to amend last commit message interactively
    # Usage: git amend-msg
    amend-msg = commit --amend

    # Stage all changes and commit (add + commit shortcut)
    # Usage: git ac "<type>(scope): description"
    # Example: git ac "fix(handlers): correct stop-loss exit logic"
    ac = "!f() { \
        if [ -z \"$1\" ]; then \
            echo \"Usage: git ac '<type>(scope): description'\"; \
            echo \"Example: git ac 'fix(handlers): correct stop-loss exit logic'\"; \
            return 1; \
        fi; \
        git add -A && git commit -m \"$1\"; \
    }; f"

    # Stage all + commit + push (full shortcut)
    # Usage: git acp "<type>(scope): description"
    # Example: git acp "feat(handlers): add volume filter"
    acp = "!f() { \
        if [ -z \"$1\" ]; then \
            echo \"Usage: git acp '<type>(scope): description'\"; \
            return 1; \
        fi; \
        git add -A && git commit -m \"$1\" && git push; \
    }; f"

    # ========================================================================
    # BRANCH INFO & STATUS
    # ========================================================================

    # Show current branch name
    # Usage: git current
    current = branch --show-current

    # Show branches with commit info
    # Usage: git branches
    branches = branch -vv

    # Show last 10 commits in one-line format
    # Usage: git last
    last = log --oneline -10

    # Show last 10 commits with color highlighting
    # Usage: git log-conv
    log-conv = log --oneline -10 --pretty=format:'%C(yellow)%h%C(reset) - %C(cyan)%s%C(reset) %C(green)(%cr)%C(reset) %C(blue)<%an>%C(reset)'

    # Show compact diff summary of staged changes
    # Usage: git staged
    staged = diff --cached --stat

    # Show compact diff summary of unstaged changes
    # Usage: git unstaged
    unstaged = diff --stat

    # Show status in short format
    # Usage: git s
    s = status -sb

    # ========================================================================
    # PROJECT SHORTCUTS
    # ========================================================================

    # Run all unit tests (pure Python, no LEAN)
    # Usage: git test
    test = "!f() { \
        echo \"Running unit tests...\"; \
        cd \"$(git rev-parse --show-toplevel)\" && \
        poetry run pytest tests/unit/ -v -o 'addopts=' 2>&1; \
    }; f"

    # Run unit tests with coverage report
    # Usage: git test-cov
    test-cov = "!f() { \
        echo \"Running unit tests with coverage...\"; \
        cd \"$(git rev-parse --show-toplevel)\" && \
        poetry run pytest tests/unit/ -v --cov=. --cov-report=term-missing --cov-report=html -o 'addopts=' 2>&1; \
    }; f"

    # Run a specific test file
    # Usage: git test-file <filename>
    # Example: git test-file test_position_manager
    test-file = "!f() { \
        if [ -z \"$1\" ]; then \
            echo \"Usage: git test-file <filename>\"; \
            echo \"Example: git test-file test_position_manager\"; \
            return 1; \
        fi; \
        cd \"$(git rev-parse --show-toplevel)\" && \
        poetry run pytest tests/unit/$1.py -v -o 'addopts=' 2>&1; \
    }; f"

    # Run a specific test by keyword match
    # Usage: git test-k <keyword>
    # Example: git test-k stop_loss
    test-k = "!f() { \
        if [ -z \"$1\" ]; then \
            echo \"Usage: git test-k <keyword>\"; \
            echo \"Example: git test-k stop_loss\"; \
            return 1; \
        fi; \
        cd \"$(git rev-parse --show-toplevel)\" && \
        poetry run pytest tests/unit/ -v -k \"$1\" -o 'addopts=' 2>&1; \
    }; f"

    # Format code with Black
    # Usage: git fmt
    fmt = "!f() { \
        echo \"Formatting code with Black...\"; \
        cd \"$(git rev-parse --show-toplevel)\" && \
        poetry run black .; \
    }; f"

    # Type check handlers with mypy
    # Usage: git typecheck
    typecheck = "!f() { \
        echo \"Running mypy type checks...\"; \
        cd \"$(git rev-parse --show-toplevel)\" && \
        poetry run mypy handlers/ config.py; \
    }; f"

    # Run full local quality gate: format + type check + tests
    # Usage: git check
    check = "!f() { \
        cd \"$(git rev-parse --show-toplevel)\" && \
        echo '=== 1/3 Formatting (Black) ===' && \
        poetry run black . && \
        echo '' && \
        echo '=== 2/3 Type Check (mypy) ===' && \
        poetry run mypy handlers/ config.py && \
        echo '' && \
        echo '=== 3/3 Unit Tests ===' && \
        poetry run pytest tests/unit/ -v -o 'addopts=' 2>&1 && \
        echo '' && \
        echo '✅ All checks passed!'; \
    }; f"
