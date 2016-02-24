#!/usr/bin/env python
from gomatic import *
import os

def _create_pipeline(group, pipeline_name, add_cf_vars=False):
	pipeline_group = configurator.ensure_pipeline_group(group)
	pipeline = pipeline_group.ensure_replacement_of_pipeline(pipeline_name)
	if(add_cf_vars == True):
		pipeline.ensure_unencrypted_secure_environment_variables({"CF_USERNAME": os.environ['CF_USERNAME'], "CF_PASSWORD": os.environ['CF_PASSWORD']})
		pipeline.ensure_environment_variables({"CF_HOME": "."})
	return pipeline

def _add_exec_task(job, command, working_dir=None, runif="passed"):
	job.add_task(ExecTask(['/bin/bash', '-l', '-c', command], working_dir=working_dir, runif=runif))

def _add_sudo_exec_task(job, command, working_dir=None, runif="passed"):
	job.add_task(ExecTask(['/bin/bash', '-c', 'sudo ' + command], working_dir=working_dir, runif=runif))

def build_csharp_pipeline_group(configurator):
	pipeline = _create_pipeline("csharp", "csharp_build")
	pipeline.set_git_url("https://github.com/wendyi/continuousSecurity")
	job = pipeline.ensure_stage("build").ensure_job("compile")
	_add_exec_task(job, '/home/vagrant/.dnx/runtimes/dnx-coreclr-linux-x64.1.0.0-rc1-update1/bin/dnu restore RecipeSharing', 'csharp')
	_add_exec_task(job, '/home/vagrant/.dnx/runtimes/dnx-coreclr-linux-x64.1.0.0-rc1-update1/bin/dnu build RecipeSharing', 'csharp')
	_add_exec_task(job, '/home/vagrant/.dnx/runtimes/dnx-coreclr-linux-x64.1.0.0-rc1-update1/bin/dnu restore RecipeSharing.UnitTests', 'csharp')
	_add_exec_task(job, '/home/vagrant/.dnx/runtimes/dnx-coreclr-linux-x64.1.0.0-rc1-update1/bin/dnu build RecipeSharing.UnitTests', 'csharp')
	job.ensure_artifacts({BuildArtifact("*", "csharp_build")})

	pipeline = _create_pipeline("csharp", "csharp_unit_test")
	pipeline.ensure_material(PipelineMaterial('csharp_build', 'build'))
	job = pipeline.ensure_stage("unit_test").ensure_job("run_tests")
	job.add_task(FetchArtifactTask('csharp_build', 'build', 'compile', FetchArtifactDir('csharp_build')))
	_add_exec_task(job, '/home/vagrant/.dnx/runtimes/dnx-coreclr-linux-x64.1.0.0-rc1-update1/bin/dnx run', 'csharp_build/csharp/RecipeSharing.UnitTests')
	job.ensure_artifacts({TestArtifact("build/test-results")})

def build_java_pipeline_group(configurator):
	pipeline = _create_pipeline("java", "java_build")
	pipeline.set_git_url("https://github.com/wendyi/continuousSecurity")
	job = pipeline.ensure_stage("build").ensure_job("compile")
	_add_exec_task(job, 'gradle --profile clean', 'java')
	_add_exec_task(job, 'gradle --profile compileJava', 'java')
	_add_exec_task(job, 'gradle --profile compileTestJava', 'java')
	job.ensure_artifacts({BuildArtifact("*", "java_build")})

	pipeline = _create_pipeline("java", "java_unit_test")
	pipeline.ensure_material(PipelineMaterial('java_build', 'build'))
	job = pipeline.ensure_stage("unit_test").ensure_job("run_tests")
	job.add_task(FetchArtifactTask('java_build', 'build', 'compile', FetchArtifactDir('java_build')))
	_add_exec_task(job, 'gradle --profile test', 'java_build/java')
	job.ensure_artifacts({TestArtifact("build/test-results")})

def build_ruby_pipeline_group(configurator):
	pipeline = _create_pipeline("ruby", "ruby_build")
	pipeline.set_git_url("https://github.com/wendyi/continuousSecurity")
	job = pipeline.ensure_stage("build").ensure_job("bundle_install")
	_add_exec_task(job, 'bundle install --path vendor/bundle', 'ruby')
	job.ensure_artifacts({BuildArtifact("*", "ruby_build")})

	pipeline = _create_pipeline("ruby", "ruby_unit_test")
	pipeline.ensure_material(PipelineMaterial('ruby_build', 'build'))
	job = pipeline.ensure_stage("unit_test").ensure_job("run_tests")
	job.add_task(FetchArtifactTask('ruby_build', 'build', 'bundle_install', FetchArtifactDir('ruby_build')))
	_add_exec_task(job, 'bundle exec rake spec:unit', 'ruby_build/ruby')
	job.ensure_artifacts({TestArtifact("spec/reports")})

def build_security_pipeline_group(configurator):
	pipeline = _create_pipeline("csharp_security", "csharp_vulnerable_components")
	pipeline.ensure_material(PipelineMaterial('csharp_build', 'build'))
	ruby_job = pipeline.ensure_stage("verify_components").ensure_job("check_csharp_dependencies")
	ruby_job.add_task(FetchArtifactTask('csharp_build', 'build', 'compile', FetchArtifactDir('csharp_build')))
	_add_sudo_exec_task(ruby_job, '/usr/local/bin/dependency-check/bin/dependency-check.sh --project "RecipeSharing" --scan "packages"', 'csharp_build/csharp')

	pipeline = _create_pipeline("java_security", "java_vulnerable_components")
	pipeline.ensure_material(PipelineMaterial('java_build', 'build'))
	java_job = pipeline.ensure_stage("verify_components").ensure_job("check_java_dependencies")
	java_job.add_task(FetchArtifactTask('java_build', 'build', 'compile', FetchArtifactDir('java_build')))
	_add_exec_task(java_job, 'gradle --profile dependencyCheck', 'java_build/java')

	pipeline = _create_pipeline("ruby_security", "ruby_vulnerable_components")
	pipeline.ensure_material(PipelineMaterial('ruby_build', 'build'))
	ruby_job = pipeline.ensure_stage("verify_components").ensure_job("check_ruby_dependencies")
	ruby_job.add_task(FetchArtifactTask('ruby_build', 'build', 'bundle_install', FetchArtifactDir('ruby_build')))
	_add_exec_task(ruby_job, 'bundle exec rake dependency_check', 'ruby_build/ruby')

configurator = GoCdConfigurator(HostRestClient("localhost:8153"))
configurator.remove_all_pipeline_groups()
build_csharp_pipeline_group(configurator)
build_java_pipeline_group(configurator)
build_ruby_pipeline_group(configurator)
build_security_pipeline_group(configurator)
configurator.save_updated_config()
