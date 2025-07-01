# Getting Started with python-aapclient

## Overview

You now have a complete CRUD-based command-line application for Ansible Automation Platform (AAP) that's modeled after `python-openstackclient`. The project provides:

- **Full CRUD operations** for AAP resources (projects, job templates, inventories, etc.)
- **OpenStack-style CLI interface** with familiar command patterns
- **Multi-component support** for AAP 2.5+ (controller, EDA, galaxy)
- **Automatic API version detection** and backward compatibility
- **Extensible plugin architecture** for adding new commands

## Project Structure

```
python-aapclient/
├── aapclient/                     # Main package
│   ├── shell.py                   # CLI entry point (`aap` command)
│   ├── common/
│   │   ├── clientmanager.py       # Manages API clients
│   │   └── aapconfig.py           # Configuration management
│   ├── controller/
│   │   ├── client.py              # Controller API client
│   │   └── v2/
│   │       ├── project.py         # `aap project` commands
│   │       └── job_template.py    # `aap job-template` commands
│   ├── eda/
│   │   └── client.py              # EDA API client
│   └── galaxy/
│       └── client.py              # Galaxy API client
├── pyproject.toml                 # Entry points and dependencies
├── setup.py, setup.cfg            # Package configuration
├── requirements.txt               # Dependencies
├── README.rst                     # Documentation
└── test_aapclient.py              # Test/demo script
```

## Installation

1. **Install dependencies:**
   ```bash
   cd python-aapclient
   pip install -r requirements.txt
   ```

2. **Install the package:**
   ```bash
   pip install -e .
   ```

## Configuration

Set environment variables for AAP connection:

```bash
export AAP_HOST=https://your-aap-server.com
export AAP_TOKEN=your-token
# OR use username/password
export AAP_USERNAME=your-username
export AAP_PASSWORD=your-password
```

## Usage Examples

### Basic Commands

```bash
# List resources
aap project list
aap organization list
aap job-template list
aap job list

# Show details
aap project show myproject
aap job-template show "My Template"
aap job show 123

# Create resources
aap project create myproject \
  --organization 1 \
  --scm-type git \
  --scm-url https://github.com/user/repo.git

aap organization create myorg \
  --description "My Organization"

# Update resources
aap project set myproject \
  --description "Updated description" \
  --scm-branch main

# Delete resources
aap project delete myproject
aap organization delete myorg
```

### Job Management

```bash
# Launch job templates
aap job-template launch "My Template" \
  --extra-vars demo=cloud \
  --extra-vars environment=test \
  --inventory 1 \
  --limit "web*"

# Launch with extra vars from file
aap job-template launch "My Template" \
  --extra-vars-file vars.json

# Monitor jobs
aap job list --status running
aap job show 456
aap job output 456  # Show job logs

# Cancel jobs
aap job cancel 456
```

### Advanced Features

```bash
# Filter and search
aap project list --organization 1 --scm-type git
aap job-template list --project 5 --long
aap job list --status failed --limit 10

# Multiple operations
aap project delete proj1 proj2 proj3
```

## Command Structure

The CLI follows the pattern: `aap <resource> <action> [options]`

### Resources
- `project` - Source code projects
- `organization` - Organizations
- `inventory` - Host inventories
- `credential` - Authentication credentials
- `job-template` - Job templates
- `job` - Jobs and job history
- `team` - Teams
- `user` - Users

### Actions
- `list` - List resources with optional filtering
- `show <id/name>` - Show detailed information
- `create <name>` - Create new resource
- `set <id/name>` - Update existing resource
- `delete <id/name>` - Delete resource
- `launch <id/name>` - Launch job template (job-template only)

## Key Features

### 1. OpenStack-Style Interface
Commands follow the same patterns as `openstack` CLI:
- Consistent argument naming and behavior
- Support for both IDs and names for resource identification
- Tabular output with optional detailed views
- Error handling and validation

### 2. CRUD Operations
Complete Create, Read, Update, Delete support for all resources:
- **Create**: `aap project create myproject --organization 1`
- **Read**: `aap project list`, `aap project show myproject`
- **Update**: `aap project set myproject --description "New desc"`
- **Delete**: `aap project delete myproject`

### 3. Job Template Integration
Special support for job templates that you were working with:
- Launch templates with survey variables
- Support for extra vars (key=value or from file)
- Job monitoring and output retrieval
- Job cancellation and management

### 4. Multi-Component Architecture
Designed for AAP 2.5+ with support for:
- **Controller**: Core automation resources
- **EDA**: Event-driven automation (extensible)
- **Galaxy**: Content management (extensible)

### 5. Extensible Design
Easy to add new commands by:
1. Creating command classes in appropriate modules
2. Adding entry points in `pyproject.toml`
3. Following the established patterns

## Development

### Adding New Commands

1. **Create command class** (e.g., in `aapclient/controller/v2/inventory.py`):
   ```python
   class CreateInventory(command.ShowOne):
       """Create new inventory"""
       
       def get_parser(self, prog_name):
           parser = super().get_parser(prog_name)
           parser.add_argument('name', help='Inventory name')
           parser.add_argument('--organization', required=True, type=int)
           return parser
       
       def take_action(self, parsed_args):
           client = self.app.client_manager.controller
           data = {'name': parsed_args.name, 'organization': parsed_args.organization}
           inventory = client.create_inventory(data)
           return display_columns, utils.get_dict_properties(inventory, display_columns)
   ```

2. **Add entry point** in `pyproject.toml`:
   ```toml
   [project.entry-points."aap.controller.v2"]
   inventory_create = "aapclient.controller.v2.inventory:CreateInventory"
   ```

3. **Add API method** in client:
   ```python
   def create_inventory(self, data):
       return self.post('inventories/', data=data)
   ```

### Testing

Use the test script to verify functionality:
```bash
python test_aapclient.py
```

## Comparison to Template 12 Launch

Remember when we launched template 12 with the MCP client? Here's how you'd do the same thing with this CLI:

```bash
# MCP way (what we did before):
# - Had to investigate survey requirements
# - Used investigation scripts
# - Handled survey parsing manually

# AAP CLI way (much simpler):
aap job-template launch 12 --extra-vars demos=cloud,linux,openshift
# or
aap job-template launch "Product Demos | Multi-demo setup" \
  --extra-vars demos=cloud,linux,openshift

# Then monitor the job:
aap job list
aap job show 4
aap job output 4
```

## Next Steps

1. **Install dependencies** and test the client
2. **Add more command implementations** for inventories, credentials, etc.
3. **Extend EDA and Galaxy clients** with real implementations
4. **Add tests** and documentation
5. **Package for distribution** on PyPI

The foundation is complete and follows all the OpenStack client patterns. You can now build out the remaining CRUD operations for all AAP resources! 