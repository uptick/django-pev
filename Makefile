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

test:
	@echo "--- 💃 Testing 💃 ---"
	python manage.py test

ci: test lint

