# API Mobilic

Dépôt de code du back de la startup d'état **Mobilic** incubée à la Fabrique Numérique du Ministère de la Transition Écologique.

Ce `README` contient essentiellement des informations pour installer un environnement de développement local du back Mobilic.

C'est plutôt [ici](https://github.com/MTES-MCT/mobilic) pour des informations concernant  :

* l'architecture logicielle du projet
* l'infrastructure et les différents technos ou outils utilisés
* le guide d'installation du front

## Pré-requis

* [Python](https://www.python.org/)
* [pip](https://pypi.org/project/pip/)
* [pipenv](https://pipenv.pypa.io/)

Note: Il est possible que vous ayez à installer aussi, sur un environnement Debian/Ubuntu,
les packages python3-dev et libpq-dev pour pouvoir installer psycopg2

## Installation

### Option 1 : Installation avec Docker (recommandée)

```sh
# Lancer tous les services (API, base de données, Redis, Celery)
docker-compose up -d
```

Cette méthode lance automatiquement :
- L'API Mobilic sur le port 5000
- PostgreSQL sur le port 5432 
- Redis sur le port 6379
- Le worker Celery

### Option 2 : Installation manuelle avec pipenv

```sh
pipenv install
pipenv shell
pre-commit install
```

Puis lancer la base de données avec Docker :
```sh
docker-compose up -d mobilic-db redis
```

## Variables d'environnement

* `DATABASE_URL` : URL de la base de données. Par défaut c'est l'URL de la base de données `mobilic` locale (telle que créée par le script d'installation)
* `MOBILIC_ENV` : environnement (dev, test, staging, prod, sandbox). "dev" par défaut
* `SIREN_API_KEY` : jeton de connexion à l'[API Sirene](https://api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/pages/item-info.jag?name=Sirene&version=V3&provider=insee) pour l'inscription entreprise. Facultatif
* `MAILJET_API_KEY` : jeton de connexion à l'API Mailjet pour l'envoi de mails. Facultatif (certaines requêtes renverront des erreurs ceci dit).
* `MAILJET_API_SECRET` : facultatif
* `FRONTEND_URL` : URL du serveur front (utilisé pour générer des liens dans des mails par exemple)
* `JWT_SECRET_KEY` : secret utilisé pour générer les jetons d'authentification. Facultatif.

Ne sont listées ici que les variables les plus importantes. L'intégralité des variables de configuration peut être trouvée dans le fichier [config.py](./config.py).

Il est possible de définir les variables d'environnement à partir d'un fichier texte qu'il faut rajouter à la racine du projet. Il faut ensuite passer le nom du fichier à l'application via la variable `DOTENV_FILE`.

```sh
DOTENV_FILE=.env flask run ...
```

Un [fichier d'exemple](./.env.example) détaille la structure attendue pour ce fichier.

## Démarrage du serveur de développement

### Avec Docker

```sh
# Si des volumes sont déja présents et  que l'on souhaite les reset
docker-compose down -v

# Pour rebuild l'image flask (si nouvelles librairies par exemple)
docker-compose up --build

# Lancer tous les services
docker-compose up

# A la suite d'un premier lancement (création de volume)
# Pour lancer les migrations et les seeds
docker exec -it mobilic-flask flask db upgrade && flask db seed
```

L'API sera accessible sur http://localhost:5000

### Avec pipenv (méthode traditionnelle)

Créer un fichier dans `.env/.env.local` avec :

```text
# use development values
SENTRY_ENVIRONMENT=development
SENTRY_SAMPLE_RATE=1
SENTRY_DSN=

# disable sending emails
DISABLE_EMAIL=true
```

Lancer le serveur de développement qui recompile à la volée :

```sh
DOTENV_FILE=.env/.env.local flask run --host 0.0.0.0
```

## Lancement des tests

### Avec Docker

```sh
docker-compose exec mobilic-api flask test
```

### Avec pipenv

```sh
flask test
```

## Gestion des migrations

L'ORM [SQLAlchemy](https://www.sqlalchemy.org/) utilise [Alembic](https://alembic.sqlalchemy.org/en/latest/) pour la gestion des migrations de la base.

Les fichiers de migration sont situés [ici](./migrations/versions).

### Avec Docker

Pour ajouter une migration :

```sh
docker-compose exec mobilic-api flask db migrate -m "message de migration"
```

ou pour créer un fichier vide de migration :

```sh
docker-compose exec mobilic-api flask db revision -m "message de migration"
```

Pour mettre à jour la DB avec les dernières migrations :

```sh
docker-compose exec mobilic-api flask db upgrade
```

### Avec pipenv

Pour ajouter une migration il y a deux possibilités :

```sh
flask db migrate -m "message de migration"
```

qui va automatiquement générer un nouveau fichier de migration à partir de l'analyse du code, ou

```sh
flask db revision -m "message de migration"
```

qui va créer un fichier vide de migration à remplir manuellement

Pour mettre à jour la DB avec les dernières migrations la commande à exécuter est la suivante :

```sh
flask db upgrade
```

## Données de test

### Avec Docker

Pour injecter des données en base :
```sh
docker-compose exec mobilic-api flask seed
```

Pour vider la base :
```sh
docker-compose exec mobilic-api flask clean
```

### Avec pipenv

Pour injecter des données en base :
```commandline
flask seed
```

Pour vider la base :
```commandline
flask clean
```

Utilisateurs créés:
* busy.admin@test.com [password]: Gérant de 10 entreprises employant chacune 10 employés

## Tâches asynchrones

On utilise `celery` pour effectuer certaines tâches de manière asynchrones pour ne pas surcharger l'application.
Par exemple l'envoi des exports excel gestionnaire (envoi de l'export par email plutôt que par téléchargement direct).

### Avec Docker

Le worker Celery est automatiquement lancé avec `docker-compose up`. Vous pouvez voir ses logs avec :

```sh
docker-compose logs -f celery-worker
```

### Avec pipenv

Un service `redis` est défini dans le `docker-compose.yml`. On peut inspecter les logs pour voir s'il fonctionne bien 
avec la commande :
```
docker logs --tail 1000 -f mobilic-api-redis-1
```

Il faut ensuite lancer le worker celery :
```
DOTENV_FILE=.env/.env.local venv/bin/celery -A app.celery worker --loglevel=info 
```
En développement, penser à relancer le worker si son implémentation change.

## Infos complémentaires

Les différentes technos/frameworks utilisés par le back sont :

* [graphene](https://graphene-python.org/) pour la couche API (GraphQL)
* [Flask](https://flask.palletsprojects.com/en/2.0.x/) comme framework web
* [SQLAlchemy](https://www.sqlalchemy.org/) comme ORM
* [XlsxWriter](https://xlsxwriter.readthedocs.io/) pour générer des fichiers Excel (.xlsx)
* [Jinja](https://jinja.palletsprojects.com/en/3.0.x/templates/) le moteur de templating de Flask (pour générer des html)
* [xhtml2pdf](https://xhtml2pdf.readthedocs.io/en/latest/index.html) pour générer des PDF

### Structure du dépôt

L'organisation s'inspire indirectement du motif Modèle-Vue-Contrôleur :

* `models` contient la représentation interne des différentes entités "métier" (utilisateurs, entreprises, activités, ...)
* `domain` contient la logique métier lorsque celle-ci devient un peu trop complexe
* `data_access` définit la structure des données exposées dans l'API
* `controllers` définit les actions de l'API
* `services` contient des services secondaires
* `templates` contient les templates html servant aux emails ou à la génération de PDF

## Intégration

* [Documentation technique de l'API](https://mobilic.beta.gouv.fr/developers)
* [Conditions d'interfaçage](https://developers.mobilic.beta.gouv.fr/conditions-dinterfacage)

## Licence

[Licence MIT](./LICENSE.txt)
