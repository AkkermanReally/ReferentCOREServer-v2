# Этап 1: Сборка зависимостей
FROM python:3.11-slim as builder

# Устанавливаем Poetry
RUN pip install poetry

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем только файлы, необходимые для установки зависимостей
COPY poetry.lock pyproject.toml ./

# Устанавливаем зависимости
RUN poetry config virtualenvs.create false && poetry install --no-root


# Этап 2: Создание финального, легковесного образа
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем установленные зависимости из образа "builder"
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Копируем исходный код нашего приложения
COPY ./rcs ./rcs
COPY ./.env ./.env
COPY ./remote_components.json ./remote_components.json
COPY ./secrets_vault.json ./secrets_vault.json

CMD ["python", "-m", "rcs.main"]
