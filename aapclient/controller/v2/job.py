"""
Job commands for AAP Controller v2 API
"""

import logging

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common import utils


LOG = logging.getLogger(__name__)


class ListJob(Lister):
    """List jobs"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--long',
            action='store_true',
            default=False,
            help='List additional fields in output'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of results (default: 20)'
        )
        parser.add_argument(
            '--status',
            help='Filter by job status (pending, waiting, running, successful, failed, error, canceled)'
        )
        parser.add_argument(
            '--job-type',
            help='Filter by job type (run, check)'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller
        
        params = {}
        if parsed_args.limit:
            params['page_size'] = parsed_args.limit
        if parsed_args.status:
            params['status'] = parsed_args.status
        if parsed_args.job_type:
            params['job_type'] = parsed_args.job_type
            
        data = client.get('jobs/', params=params)
        
        # Process the data to replace IDs with names
        for job in data.get('results', []):
            # Extract job template name from summary_fields
            if 'summary_fields' in job and 'job_template' in job['summary_fields']:
                job['job_template_name'] = job['summary_fields']['job_template']['name']
            else:
                job['job_template_name'] = str(job.get('job_template', ''))
            
            # Extract inventory name from summary_fields
            if 'summary_fields' in job and 'inventory' in job['summary_fields']:
                job['inventory_name'] = job['summary_fields']['inventory']['name']
            else:
                job['inventory_name'] = str(job.get('inventory', ''))
            
            # Extract project name from summary_fields
            if 'summary_fields' in job and 'project' in job['summary_fields']:
                job['project_name'] = job['summary_fields']['project']['name']
            else:
                job['project_name'] = str(job.get('project', ''))
        
        if parsed_args.long:
            columns = ('ID', 'Name', 'Status', 'Started', 'Finished', 'Elapsed', 'Job Template', 'Inventory')
            column_headers = columns
        else:
            columns = ('ID', 'Name', 'Status', 'Started', 'Finished')
            column_headers = columns

        jobs = []
        for job in data.get('results', []):
            job_info = [
                job['id'],
                job.get('name', ''),
                job.get('status', ''),
                utils.format_datetime(job.get('started')),
                utils.format_datetime(job.get('finished')),
            ]
            
            if parsed_args.long:
                job_info.extend([
                    utils.format_duration(job.get('started'), job.get('finished')),
                    job.get('job_template_name', ''),
                    job.get('inventory_name', ''),
                ])
            
            jobs.append(job_info)

        return (column_headers, jobs)


class ShowJob(ShowOne):
    """Display job details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'job',
            help='Job ID to display'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller
        
        job_id = parsed_args.job
        data = client.get(f'jobs/{job_id}/')
        
        # Add names from summary_fields
        if 'summary_fields' in data and 'job_template' in data['summary_fields']:
            data['job_template_name'] = data['summary_fields']['job_template']['name']
        else:
            data['job_template_name'] = str(data.get('job_template', ''))
        
        if 'summary_fields' in data and 'inventory' in data['summary_fields']:
            data['inventory_name'] = data['summary_fields']['inventory']['name']
        else:
            data['inventory_name'] = str(data.get('inventory', ''))
        
        if 'summary_fields' in data and 'project' in data['summary_fields']:
            data['project_name'] = data['summary_fields']['project']['name']
        else:
            data['project_name'] = str(data.get('project', ''))
        
        if 'summary_fields' in data and 'execution_environment' in data['summary_fields']:
            data['execution_environment_name'] = data['summary_fields']['execution_environment']['name']
        else:
            data['execution_environment_name'] = str(data.get('execution_environment', ''))
        
        if 'summary_fields' in data and 'instance_group' in data['summary_fields']:
            data['instance_group_name'] = data['summary_fields']['instance_group']['name']
        else:
            data['instance_group_name'] = str(data.get('instance_group', ''))
        
        # Format the data for display
        display_data = []
        fields = [
            'id', 'name', 'description', 'status', 'failed', 'started', 'finished',
            'elapsed', 'job_template_name', 'job_type', 'inventory_name', 'project_name', 'playbook',
            'forks', 'limit', 'verbosity', 'extra_vars', 'job_tags', 'skip_tags',
            'execution_node', 'controller_node', 'execution_environment_name', 'instance_group_name',
            'launched_by', 'created', 'modified', 'created_by', 'modified_by'
        ]
        
        for field in fields:
            value = data.get(field, '')
            if field in ['started', 'finished', 'created', 'modified']:
                value = utils.format_datetime(value)
            elif field == 'elapsed':
                value = utils.format_duration(data.get('started'), data.get('finished'))
            elif field == 'launched_by':
                # Format launched_by data to show user name
                if isinstance(value, dict) and 'name' in value:
                    value = value['name']
                elif value is None or value == '':
                    value = 'N/A'
            elif isinstance(value, bool):
                value = str(value)
            elif value is None:
                value = ''
                
            display_data.append((field.replace('_', ' ').title(), value))
        
        return zip(*display_data) if display_data else ((), ())


class CancelJob(Command):
    """Cancel a running job"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'job',
            help='Job ID to cancel'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller
        
        job_id = parsed_args.job
        
        # Check if job exists and is cancelable
        job_data = client.get(f'jobs/{job_id}/')
        if job_data.get('status') not in ['pending', 'waiting', 'running']:
            self.app.stdout.write(f"Job {job_id} cannot be canceled (status: {job_data.get('status')})\n")
            return
        
        # Cancel the job
        client.post(f'jobs/{job_id}/cancel/')
        self.app.stdout.write(f"Job {job_id} cancellation requested\n")


class RelaunchJob(ShowOne):
    """Relaunch a job"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'job',
            help='Job ID to relaunch'
        )
        parser.add_argument(
            '--extra-vars',
            help='Extra variables to pass to the job (JSON format)'
        )
        parser.add_argument(
            '--limit',
            help='Limit execution to specific hosts'
        )
        parser.add_argument(
            '--job-tags',
            help='Job tags to run'
        )
        parser.add_argument(
            '--skip-tags',
            help='Job tags to skip'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller
        
        job_id = parsed_args.job
        
        # Prepare relaunch data
        relaunch_data = {}
        if parsed_args.extra_vars:
            relaunch_data['extra_vars'] = parsed_args.extra_vars
        if parsed_args.limit:
            relaunch_data['limit'] = parsed_args.limit
        if parsed_args.job_tags:
            relaunch_data['job_tags'] = parsed_args.job_tags
        if parsed_args.skip_tags:
            relaunch_data['skip_tags'] = parsed_args.skip_tags
        
        # Relaunch the job
        response = client.post(f'jobs/{job_id}/relaunch/', data=relaunch_data)
        
        # Display the new job information
        new_job = response
        display_data = [
            ('New Job ID', new_job['id']),
            ('Name', new_job.get('name', '')),
            ('Status', new_job.get('status', '')),
            ('Job Template', new_job.get('job_template', '')),
            ('Created', utils.format_datetime(new_job.get('created'))),
        ]
        
        return zip(*display_data) if display_data else ((), ())


class ShowJobOutput(Command):
    """Show job output/logs"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'job',
            help='Job ID to show output for'
        )
        parser.add_argument(
            '--follow',
            action='store_true',
            default=False,
            help='Follow job output (for running jobs)'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller
        
        job_id = parsed_args.job
        
        # Get job events (output)
        try:
            # Get job events which contain the actual output
            events_data = client.get(f'jobs/{job_id}/job_events/')
            
            if not events_data.get('results'):
                self.app.stdout.write("No output available for this job\n")
                return
            
            # Display the events in chronological order
            for event in events_data['results']:
                if event.get('stdout'):
                    timestamp = utils.format_datetime(event.get('created'))
                    self.app.stdout.write(f"[{timestamp}] {event['stdout']}\n")
                    
        except Exception as e:
            # Fallback to job stdout if events aren't available
            try:
                stdout_data = client.get(f'jobs/{job_id}/stdout/')
                if stdout_data:
                    self.app.stdout.write(stdout_data)
                else:
                    self.app.stdout.write("No output available for this job\n")
            except Exception:
                self.app.stdout.write(f"Failed to retrieve job output: {e}\n") 