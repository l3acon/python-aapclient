==================
python-aapclient
==================

Ansible Automation Platform Command-line Client

python-aapclient is a command-line client for Ansible Automation Platform (AAP) that provides a unified interface for managing AAP resources such as projects, job templates, inventories, credentials, and more.

This project is modeled after python-openstackclient and follows similar patterns for command structure and organization.

⚠️  This tool is under active development, features may not work entirely or as expected.  Use at your own risk!! ⚠️

Features
========

* Complete CRUD operations for AAP resources
* Automatic API version detection

Installation
============

.. code-block:: bash

    pip install python-aapclient

Configuration
=============

Configure the AAP connection using either environment variables or an ``.env`` file.  Connection information may also be passed as command-line arguments.

Option 2: Environment variables (Recommended)
---------------------------------------------

.. code-block:: bash

    export AAP_HOST=https://your-aap-host.com
    # use token authentication
    export AAP_TOKEN=your-token
    # OR use user authentication
    export AAP_USERNAME=your-username
    export AAP_PASSWORD=your-password

Option 2: .env file
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
    aap template launch "My Job Template" --extra-vars key=value

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
* ``aap inventory`` - Manage inventories
* ``aap credential`` - Manage credentials
* ``aap template`` - Manage job templates
* ``aap job`` - Manage and monitor jobs

Each resource supports standard CRUD operations where applicable:

* ``list`` - List all resources
* ``show`` - Show details of a specific resource
* ``create`` - Create a new resource
* ``set`` - Update an existing resource
* ``delete`` - Delete a resource

License
=======

Apache License 2.0 
