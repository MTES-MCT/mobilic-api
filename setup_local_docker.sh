#!/usr/bin/env bash

set -e

ROOT_PROJECT_DIR=`dirname "$(python -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "${BASH_SOURCE[0]}")"`
cd ${ROOT_PROJECT_DIR}

# Step 1 : install virtual env

if [ -z "$VIRTUAL_ENV" ]; then
  VIRTUAL_ENV_FOLDER=${ROOT_PROJECT_DIR}/venv
  echo "Creating or using the virtual environment at $VIRTUAL_ENV_FOLDER"
  python3 -m venv ${VIRTUAL_ENV_FOLDER}
else
  VIRTUAL_ENV_FOLDER=$VIRTUAL_ENV
  echo "Using detected virtual environment at $VIRTUAL_ENV_FOLDER"
fi

COMMENT='#Enabling Flask CLI...'
EXPORT_STMT="
export FLASK_APP=app:app
export FLASK_DEBUG=1
export FLASK_SKIP_DOTENV=1
"

# Step 2 : enable flask CLI upon venv activation

echo "Enabling Flask CLI..."
ACTIVATE_PATH=${VIRTUAL_ENV_FOLDER}/bin/activate
if grep --quiet "$COMMENT" $ACTIVATE_PATH; then
  echo -e "Flask CLI is already enabled!"
else
  echo -en "\n$COMMENT" >> $ACTIVATE_PATH
  echo -e "$EXPORT_STMT" >> $ACTIVATE_PATH
fi

# Step 3 : install dependencies

echo "Installing dependencies..."
source ${VIRTUAL_ENV_FOLDER}/bin/activate
pip install --quiet -r requirements.txt

# Step 4 : installing pre-commit hooks

echo "Installing pre-commit"
pre-commit install

# Step 5 : apply modifications
deactivate
source ${VIRTUAL_ENV_FOLDER}/bin/activate

# Step 6 : create database on docker postgres
echo "Creating local database mobilic (if needed)..."
docker-compose up -d

# Step 7 : run migrations
echo "Running DB migrations..."
flask db upgrade 1> /dev/null

echo "All good ! You are all set"
