# API Mobilic

Dépôt de code du back de la startup d'état **Mobilic** incubée à la Fabrique Numérique du Ministère de la Transition Écologique.

Ce `README` contient essentiellement des informations pour installer un environnement de développement local du back Mobilic.

C'est plutôt [ici](https://github.com/MTES-MCT/mobilic) pour des informations concernant  :

* l'architecture logicielle du projet
* l'infrastructure et les différents technos ou outils utilisés
* le guide d'installation du front

## Pré-requis

* [Python](https://www.python.org/) 3.9
* [pip](https://pypi.org/project/pip/) 21.2
* [PostgreSQL](https://www.postgresql.org/) 12.0, avec sa ligne de commande `psql`

## Installation

Démarrer un serveur PostgreSQL local.

Exécuter le script d'installation depuis la racine du projet :

```sh
./setup_local_docker.sh
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

```sh
flask test
```

## Gestion des migrations

L'ORM [SQLAlchemy](https://www.sqlalchemy.org/) utilise [Alembic](https://alembic.sqlalchemy.org/en/latest/) pour la gestion des migrations de la base.

Les fichiers de migration sont situés [ici](./migrations/versions).

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

Pour injecter des données en base
```commandline
flask seed
```
Utilisateurs créés:
* busy.admin@test.com [password]: Gérant de 10 entreprises employant chacune 10 employés

Pour vider la base
```commandline
flask clean
```

## Tâches asynchrones
On utilise `celery` pour effectuer certaines tâches de manière asynchrones pour ne pas surcharger l'application.
Par exemple l'envoi des exports excel gestionnaire (envoi de l'export par email plutôt que par téléchargement direct).

Un service `redis` est défini dans le `docker-compose.yml`. On peut inspecter les logs pour voir s'il fonctionne bien 
avec la commande
```
docker logs --tail 1000 -f mobilic-api-redis-1
```
Il faut ensuite lancer le worker celery:
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
