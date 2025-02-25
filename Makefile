format:
	@echo "--- 🐶 Ruff Format 🐶 ---"
	uv run ruff format .

ruff:
	@echo "--- 🐶 Ruff Lint 🐶 ---"
	uv run ruff check . --fix

lint: ruff

postgres:
	docker compose up -d
	until psql postgres://postgres@localhost:5435/example -c 'select 1'; do sleep 2; done

test: postgres
	@echo "--- 💃 Testing 💃 ---"
	uv run python manage.py test

publish: ci
	# poetry config pypi-token.pypi your-api-token
	uv build
	uv publish

ci: test lint

