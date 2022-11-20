isort:
	@echo "--- 🐍 Isorting 🐍 ---"
	poetry run isort example test django_pev

flake8:
	@echo "--- 👏 Flaking 👏 ---"
	poetry run flake8

black:
	@echo "--- 🎩 Blacking 🎩 ---"
	poetry run black . --check

mypy:
	@echo "--- ⚡ Mypying ⚡ ---"
	poetry run mypy

lint: isort flake8 black mypy

postgres:
	docker-compose up -d
	until psql postgres://postgres@localhost:5435/example -c 'select 1'; do sleep 2; done

test: postgres
	@echo "--- 💃 Testing 💃 ---"
	poetry run python manage.py test

publish:ci
	poetry run --publish

ci: test lint

