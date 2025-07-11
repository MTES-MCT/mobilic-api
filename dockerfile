FROM python:3.13-slim

# Install system dependencies
# RUN apt-get update && apt-get install -y \
#     gcc libpq-dev libffi-dev build-essential libxml2-dev libxslt-dev \
#     libjpeg-dev zlib1g-dev libtiff-dev libfreetype6-dev liblcms2-dev libwebp-dev \
#     && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    gcc build-essential libpq-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the application code
WORKDIR /app
COPY . .

# Install pipenv and dependencies
RUN python -m pip install --upgrade pip && pip install pipenv
RUN pipenv install --system --dev

# Run DB migrations and start the app
CMD ["flask", "run", "--host", "0.0.0.0"]