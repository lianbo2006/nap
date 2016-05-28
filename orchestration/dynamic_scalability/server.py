# coding=utf-8

from orchestration.database import database_update
from orchestration.nap_api import app_info
from orchestration.container_api.client import Client
from orchestration.container_api.container import Container
from orchestration.container_api.network import Network
from orchestration import config
from orchestration import schedule


def service_load_calculate(username, project_name, service_name):
    service_usage = app_info.service_monitor(username, project_name, service_name)

    if service_usage is None:
        return 0, 0
    cpu_usage = 0
    mem_usage = 0

    for usage in service_usage:
        container_usage = usage['list']
        cpu_usage += int(container_usage[-1]['cpu_usage'])
        mem_usage += int(container_usage[-1]['mem_usage'])

    service_scale = len(service_usage)

    return cpu_usage/service_scale, mem_usage/service_scale


def scale_up(username, project_name, service_name):
    service_scale, service_dict = database_update.get_service_scale_config(username, project_name, service_name)

    true = True
    false = False
    service_dict = eval(service_dict)

    print service_scale
    print service_dict

    ip = schedule.random_schedule()
    client = Client(ip, config.c_version)

    container_name = service_name + "_" + str(service_scale)
    service_dict['container_name'] = container_name + config.split_mark + project_name + config.split_mark + username
    cont = Container(client=client, options=service_dict, volume=None, network=Network(service_dict['network']))
    cont.create()
    cont.start()

    database_update.create_container(username, project_name, service_name, container_name, ip)
    database_update.set_service_scale(username, project_name, service_name, int(service_scale)+1)
    # TODO check does consul-templates reload nginx successfully


def scale_down(username, project_name, service_name):
    service_scale, service_config = database_update.get_service_scale_config(username, project_name, service_name)

    service_scale = int(service_scale) - 1
    container_name = service_name + "_" + str(service_scale)
    full_name = container_name + config.split_mark + project_name + config.split_mark + username

    print full_name

    ip = database_update.container_ip(username, project_name, service_name, container_name)
    client = Client(ip, config.c_version)

    cont = Container.get_container_by_name(client, full_name)
    cont.stop()
    cont.remove()

    database_update.delete_container_by_name(username, project_name, service_name, container_name)
    database_update.set_service_scale(username, project_name, service_name, service_scale)