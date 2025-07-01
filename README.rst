==================
python-aapclient
==================

Ansible Automation Platform Command-line Client

python-aapclient is a command-line client for Ansible Automation Platform (AAP) that provides a unified interface for managing AAP resources such as projects, job templates, inventories, credentials, and more.

This project is modeled after python-openstackclient and follows similar patterns for command structure and organization.

Features
========

* Complete CRUD operations for AAP resources
* Support for AAP 2.4+ and AAP 2.5+ (multi-component architecture)
* Automatic API version detection
* Command-line interface similar to OpenStack client
* Extensible plugin architecture

Installation
============

.. code-block:: bash

    pip install python-aapclient

Configuration
=============

Configure AAP connection using either a ``.env`` file or environment variables.

Option 1: .env file (Recommended)
----------------------------------

Create a ``.env`` file in your project directory:

.. code-block:: bash

    # Copy the example and edit with your details
    cp env.example .env

Example ``.env`` file:

.. code-block:: bash

    # Required
    AAP_HOST=https://your-aap-host.com
    AAP_TOKEN=your-api-token

    # OR use username/password
    # AAP_USERNAME=your-username  
    # AAP_PASSWORD=your-password

    # Optional
    AAP_VERIFY_SSL=false  # For self-signed certificates
    AAP_CA_BUNDLE=/path/to/ca-bundle.crt
    AAP_TIMEOUT=60  # Request timeout in seconds

Option 2: Environment variables
--------------------------------

.. code-block:: bash

    export AAP_HOST=https://your-aap-host.com
    export AAP_USERNAME=your-username
    export AAP_PASSWORD=your-password
    # OR use token authentication
    export AAP_TOKEN=your-token

Usage
=====

Basic commands:

.. code-block:: bash

    # List projects
    aap project list

    # Show project details
    aap project show myproject

    # Create a new project
    aap project create myproject --scm-type git --scm-url https://github.com/user/repo.git

    # Launch a job template
    aap job template launch "My Job Template" --extra-vars key=value

    # List jobs
    aap job list

    # Show job output
    aap job output 123

Commands
========

The client organizes commands by AAP component and resource type:

Controller Commands
-------------------

* ``aap project`` - Manage projects
* ``aap organization`` - Manage organizations  
* ``aap inventory`` - Manage inventories
* ``aap credential`` - Manage credentials
* ``aap job-template`` - Manage job templates
* ``aap job`` - Manage and monitor jobs
* ``aap team`` - Manage teams
* ``aap user`` - Manage users

EDA Commands
------------

* ``aap eda-rulebook`` - Manage EDA rulebooks
* ``aap eda-activation`` - Manage EDA activations

Galaxy Commands
---------------

* ``aap galaxy-collection`` - Manage Galaxy collections
* ``aap galaxy-namespace`` - Manage Galaxy namespaces

Each resource supports standard CRUD operations where applicable:

* ``list`` - List all resources
* ``show`` - Show details of a specific resource
* ``create`` - Create a new resource
* ``set`` - Update an existing resource
* ``delete`` - Delete a resource

Contributing
============

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

License
=======

Apache License 2.0 