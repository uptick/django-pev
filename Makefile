format:
	@echo "--- 🐶 Ruff Format 🐶 ---"
	poetry run ruff format .

ruff:
	@echo "--- 🐶 Ruff Lint 🐶 ---"
	poetry run ruff check . --fix

lint: ruff

postgres:
	docker-compose up -d
	until psql postgres://postgres@localhost:5435/example -c 'select 1'; do sleep 2; done

test: postgres
	@echo "--- 💃 Testing 💃 ---"
	poetry run python manage.py test

publish: ci
	poetry publish --build

ci: test lint

