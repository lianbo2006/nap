# coding=utf-8
import commands
import MySQLdb
import requests
import time
from fs.osfs import OSFS
from docker import Client as dClient

from orchestration import config
from orchestration.database import database_update
from orchestration.container_api.container import Container
from orchestration.project import Project
from orchestration.container_api.network import Network
from orchestration.container_api.client import Client


def tuple_in_tuple(db_tuple):
    ret_data = []
    for item in db_tuple:
        ret_data.append(item[0])
    return ret_data


def create_user(username, email):
    # for client in config.client_list:
        # still need mfsmount
        # commands.getstatusoutput("ssh %s@%s 'docker run -d --name %s -v %s/%s:%s %s'" % (
            # config.hostname, client.split(":")[0], username + "_volume", config.project_path, username,
            # config.container_path, config.volume_image))

    commands.getstatusoutput("ssh %s@%s 'docker network create -d overlay %s'" % (
        config.hostname, config.client_list[0].split(":")[0], username))
    commands.getstatusoutput("ssh %s@%s 'cd %s && mkdir %s'" % (
        config.hostname, config.client_list[0].split(":")[0], config.project_path, username))

    return database_update.create_user(username, email)


def delete_user(username):
    try:
        database_update.delete_user(username)
    except MySQLdb.OperationalError as e:
        return False, e.message

    for client in config.client_list:
        # still need mfsmount
        commands.getstatusoutput(
            "ssh %s@%s 'docker rm %s'" % (config.hostname, client.split(":")[0], username + "_volume"))

    commands.getstatusoutput(
        "ssh %s@%s 'cd %s && rm -r %s'" % (config.hostname, client.split(":")[0], config.project_path, username))
    a, b = commands.getstatusoutput(
        "ssh %s@%s 'docker network rm %s'" % (config.hostname, config.client_list[0].split(":")[0], username))

    return True, 'Delete user success'


def project_list(username, begin, length):
    data = database_update.project_list(username, begin, length)
    return data


def get_project(username, project_name):
    data = database_update.get_project(username, project_name)
    return data


def kill_project(username, project_name):
    project = Project.get_project_by_name(username, project_name)
    project.kill()


def destroy_project(username, project_name):

    user_path = config.project_path + "/" + username
    home_dir = OSFS(user_path)
    if home_dir.exists(project_name):
        home_dir.removedir(project_name, force=True)

    project = Project.get_project_by_name(username, project_name)
    if project is None:
        return 'project not found'
    project.stop()
    project.remove()

    database_update.delete_project(username, project_name)
    database_update.delete_service_for_scale(username, project_name)

    return 'success'


def restart_project(username, project_name):
    project = Project.get_project_by_name(username, project_name)
    project.restart()


def service_list(username, project_name):
    data = database_update.service_list(username, project_name)
    return data


def get_service(username, project_name, service_name):
    data = database_update.get_service(username, project_name, service_name)
    return data


def kill_service(username, project_name, service_name):
    return 'todo'


def destroy_service(username, project_name, service_name):
    return 'todo'


def restart_service(username, project_name, service_name):
    return 'todo'


def container_list(username, project_name, service_name):
    name_list = database_update.container_list(username, project_name, service_name)

    if name_list is None:
        return None

    data = []
    for container_name in name_list:
        data.append(get_container(username, project_name, service_name, container_name[0]))

    return data


def get_container(username, project_name, service_name, container_name):
    url = database_update.container_ip(username, project_name, service_name, container_name)
    full_name = container_name + config.split_mark + project_name + config.split_mark + username

    cli = Client(url, config.c_version)
    con = Container.get_container_by_name(cli, full_name)

    srv_dict = {'name': container_name, 'ip': str(url).split(":")[0]}

    if con is None:
        srv_dict['status'] = 'not create'
        srv_dict['ports'] = '-'
        srv_dict['image'] = '-'
        srv_dict['create_time'] = '-'
        srv_dict['id'] = '-'
    else:
        srv_dict['status'] = con.status
        srv_dict['image'] = con.image
        srv_dict['create_time'] = con.create_time
        srv_dict['id'] = con.id
        if len(con.ports) == 0:
            srv_dict['shell'] = '-'
            ports = '-'
        else:
            ports = con.ports
            if '4200' in con.ports:
                srv_dict['shell'] = con.ports['4200']
                del ports['4200']

        srv_dict['ports'] = ports

    return srv_dict


def kill_container(username, project_name, service_name, container_name):
    ip = database_update.container_ip(username, project_name, service_name, container_name)
    client = Client(ip, config.c_version)
    full_name = container_name + config.split_mark + project_name + config.split_mark + username
    cont = Container.get_container_by_name(client, full_name)
    cont.kill()


def destroy_container(username, project_name, service_name, container_name):
    ip = database_update.container_ip(username, project_name, service_name, container_name)
    client = Client(ip, config.c_version)
    full_name = container_name + config.split_mark + project_name + config.split_mark + username
    cont = Container.get_container_by_name(client, full_name)
    cont.remove()


def restart_container(username, project_name, service_name, container_name):
    ip = database_update.container_ip(username, project_name, service_name, container_name)
    client = Client(ip, config.c_version)
    full_name = container_name + config.split_mark + project_name + config.split_mark + username
    cont = Container.get_container_by_name(client, full_name)
    cont.restart()


def service_name_list(username, project_name):
    data = database_update.service_list(username, project_name)

    return data


# def service_list(username, project_name):
#     name_list = database_update.service_list(username, project_name)
#     if name_list is None:
#         return '-'
#
#     srv_list = []
#     for service_name in name_list:
#         url = database_update.service_ip(username, project_name, service_name[0])
#         full_name = service_name[0] + config.split_mark + project_name + config.split_mark + username
#
#         cli = Client(url, config.c_version)
#         con = Container.get_container_by_name(cli, full_name)
#
#         # if not container_exists(cli, full_name):
#         #     print 'no container: %s in hosts' % full_name
#         #     continue
#
#         srv_dict = {'name': service_name[0], 'ip': str(url).split(":")[0]}
#
#         if con is None:
#             srv_dict['status'] = 'not create'
#             srv_dict['ports'] = '-'
#             srv_dict['image'] = '-'
#             srv_dict['create_time'] = '-'
#             srv_dict['id'] = '-'
#         else:
#             srv_dict['status'] = con.status
#             srv_dict['image'] = con.image
#             srv_dict['create_time'] = con.create_time
#             srv_dict['id'] = con.id
#             if len(con.ports) == 0:
#                 srv_dict['shell'] = '-'
#                 ports = '-'
#             else:
#                 ports = con.ports
#                 if '4200' in con.ports:
#                     srv_dict['shell'] = con.ports['4200']
#                     del ports['4200']
#
#             srv_dict['ports'] = ports

        # ports = get_port(username, password, project_name, service_name)
        # if ports is None:
        #     srv_dict['port'] = '-'
        #     srv_dict['shell'] = '-'
        # elif not len(ports):
        #     srv_dict['port'] = '-'
        #     srv_dict['shell'] = '-'
        # else:
        #     expose_port = []
        #     for key in ports:
        #         if not ports[key] is None:
        #             if key == '4200/tcp':
        #                 srv_dict['shell'] = ports[key][0]['HostPort']
        #             else:
        #                 expose_port.append(ports[key][0]['HostPort'])
        #         else:
        #             expose_port.append('-')
        #     srv_dict['port'] = expose_port

        # srv_list.append(srv_dict)
    # return srv_list


def get_project_service(username, project_name):
    services = []

    service_name = service_name_list(username, project_name)

    if service_name is None:
        return None

    for service in service_name:
        ip = database_update.service_ip(username, project_name, service[0])
        item = {"name": service[0] + config.split_mark + project_name + config.split_mark + username, "ip": ip}
        services.append(item)

    return services


# 注意，这里以后用project stop 来实现
# 已经用project stop 实现
# def destroy_project(username, project_name):
#     user_path = config.project_path + "/" + username
#     home_dir = OSFS(user_path)
#     if home_dir.exists(project_name):
#         home_dir.removedir(project_name, force=True)
#
#     services = get_project_service(username, project_name)
#
#     if services is None:
#         return True, 'OK'
#
#     project = Project.get_project_by_name(project_name, services)
#     project.stop()
#     project.remove()
#
#     delete_from_ct(project_name, username)
#
#     # data = database_update.service_list(username, project_name)
#     #
#     # if data:
#     #     for service_name in data:
#     #         url = str(database_update.service_ip(username, project_name, service_name))
#     #         if url == '-':
#     #             continue
#     #         cli = Client(url, config.c_version)
#     #         full_name = username + config.split_mark + project_name + config.split_mark + service_name
#     #         con = Container.getContainerByName(cli, full_name)
#     #         con.stop
#     #         if container_exists(cli, full_name):
#     #             cli.stop(container=full_name)
#     #             cli.remove_container(container=full_name)
#
#     database_update.delete_services(username, project_name)
#     database_update.delete_project(username, project_name)
#
#     return True, 'Destroy project: %s success' % project_name


# def delete_from_ct(project_name, username):
#     machines = database_update.get_machines()
#     for machine in machines:
#         cli = dClient(base_url=machine, version=config.c_version)
#         tt = cli.exec_create(container='nginx',
#                              cmd='/bin/bash -c \"cd /etc/consul-templates && bash delete.sh %s-%s\"' % (
#                                  project_name, username))
#         cli.exec_start(exec_id=tt, detach=True)


# not use again
def get_status(username, password, project_name, service_name):
    cip = database_update.service_ip(username, project_name, service_name)
    if cip == '-':
        return 'no such project or service'

    cli = Client(cip, config.c_version)
    full_name = service_name + config.split_mark + project_name + config.split_mark + username
    # full_name = username + config.split_mark + project_name + config.split_mark + service_name

    if container_exists(cli, full_name):
        detail = cli.inspect_container(full_name)
        return detail['State']['Status']
    else:
        return 'no such container'


# not use again
def get_port(username, project_name, service_name):
    cip = database_update.service_ip(username, project_name, service_name)
    if cip == '-':
        return 'no such project or service'

    cli = Client(base_url=cip, version=config.c_version)
    full_name = username + config.split_mark + project_name + config.split_mark + service_name

    if container_exists(cli, full_name):
        detail = cli.inspect_container(full_name)
        return detail['NetworkSettings']['Ports']
    else:
        return 'no such container'


def container_exists(cli, container_name):
    containers = cli.containers(all=True)
    for k in containers:
        if '/' + container_name in k['Names']:
            return True
    return False


def get_logs(username, project_name, service_name, container_name):
    cip = database_update.container_ip(username, project_name, service_name, container_name)

    print cip

    if cip == '-':
        return 'no such project or service'

    cli = Client(cip, config.c_version)
    full_name = container_name + config.split_mark + project_name + config.split_mark + username

    con = Container.get_container_by_name(cli, full_name)

    print con.id

    return con.client.logs(container=con.id, tail=100)

    # if container_exists(cli, full_name):
    #     logs = cli.logs(container=full_name)
    #     return logs
    # else:
    #     return 'no such container'


def machine_monitor():
    machines = database_update.get_machines()

    info = []

    for machine in machines:
        ip = machine.split(":")[0]
        url = 'http://' + ip + ":8080/api/v1.2/containers"
        # url = 'http://114.212.189.147:8080/api/v1.2/containers'
        response = requests.get(url)

        true = True
        false = False

        di = eval(response.text)

        cur = di['stats'][-1]
        pre = di['stats'][-2]

        gap = time_gap(pre['timestamp'], cur['timestamp'])

        core = int(di['spec']['cpu']['mask'].split("-")[1]) + 1
        print (core)

        print (gap)
        print (float(cur['cpu']['usage']['total']) - float(pre['cpu']['usage']['total']))

        dic = {'mem_usage': cur['memory']['usage'],
               'mem_total': di['spec']['memory']['limit'],
               'cpu_usage': (float(cur['cpu']['usage']['total']) - float(pre['cpu']['usage']['total'])) / (gap * core),
               'timestamp': cur['timestamp'],
               'ip': ip}

        usage = 0
        total = 0
        for item in cur['filesystem']:
            usage += item['usage']
            total += item['capacity']
            # file_dic = {'filesystem_usage': item['usage'],
            #             'filesystem_total': item['capacity']}

            # files.append(file_dic)

        dic['filesystem_usage'] = usage
        dic['filesystem_total'] = total

        info.append(dic)

    return info


def container_monitor(username, project_name, service_name, container_name):
    machine = database_update.container_ip(username, project_name, service_name, container_name)
    if machine is None:
        return 'no this project or service'

    full_name = container_name + config.split_mark + project_name + config.split_mark + username
    ip = machine.split(":")[0]
    url = 'http://' + ip + ":8080/api/v1.2/docker/" + full_name

    response = requests.get(url)

    if response.status_code == 500:
        return None

    true = True
    false = False

    di = eval(response.text)
    rel = []

    for item in di:
        for node in di[item]['stats']:
            dic = {'mem_usage': node['memory']['usage'],
                   'mem_total': di[item]['spec']['memory']['limit'],
                   'cpu_usage': node['cpu']['usage']['total'],
                   'cpu_total': di[item]['spec']['cpu']['limit'],
                   'timestamp': node['timestamp']}

            # file_usage = []
            # file_total = []
            # for files in node['filesystem']:
            #     file_usage.append(files['usage'])
            #     file_total.append(files['capacity'])
            #
            # dic['file_usage'] = file_usage
            # dic['file_total'] = file_total

            rel.append(dic)

    re = []

    for index in range(len(rel)):
        if not index == 0:
            pre = rel[index - 1]
            cur = rel[index]

            gap = time_gap(pre['timestamp'], cur['timestamp'])

            dic = {'timestamp': cur['timestamp'],
                   # 'file_usage': float(cur['file_usage'])/float(cur['file_total']),
                   # 'memory_usage': float(cur['memory_usage'])float(cur['memory_total']),
                   'mem_usage': float(cur['mem_usage']),
                   'cpu_usage': (float(cur['cpu_usage']) - float(pre['cpu_usage'])) / gap}

            re.append(dic)

    return re


def container_resource_usage(username, project_name, service_name, container_name):
    machine = database_update.container_ip(username, project_name, service_name, container_name)
    if machine is None:
        return 'no this project or service'

    full_name = container_name + config.split_mark + project_name + config.split_mark + username
    ip = machine.split(":")[0]
    url = 'http://' + ip + ":8080/api/v1.2/docker/" + full_name

    response = requests.get(url)

    if response.status_code == 500:
        return None

    true = True
    false = False

    di = eval(response.text)
    rel = []

    for item in di:
        for node in di[item]['stats']:
            dic = {'mem_usage': node['memory']['usage'],
                   'mem_total': di[item]['spec']['memory']['limit'],
                   'cpu_usage': node['cpu']['usage']['total'],
                   'cpu_total': di[item]['spec']['cpu']['limit'],
                   'timestamp': node['timestamp']}

            rel.append(dic)

    if len(rel) < 2:
        return None;

    gap = time_gap(rel[-2]['timestamp'], rel[-1]['timestamp'])

    dic = {"mem_usage": float(rel[-1]["mem_usage"]/rel[-1]["mem_total"]),
            "cpu_usage": (float(rel[-1]['cpu_usage']) - float(rel[-2]['cpu_usage'])) / gap}

    return dic


def service_monitor(username, project_name, service_name):
    containers = database_update.container_list(username, project_name, service_name)

    if containers is None:
        return None

    rel = []
    for container_name in containers:
        con_monitor = container_monitor(username, project_name, service_name, container_name[0])
        if con_monitor is None:
            continue
        rel.append({'container_name': container_name[0], 'list': con_monitor})

    return rel


def project_monitor(username, project_name):
    services = database_update.service_list(username, project_name)
    rel = []
    for service in services:
        print service[0]
        container_ll = database_update.container_list(username, project_name, service[0])
        if container_ll is None:
            continue
        for container in container_ll:
            if container is None:
                continue
            con_monitor = container_monitor(username, project_name, service[0], container[0])
            if con_monitor is None:
                continue
            rel.append({'container_name': container[0], 'list': con_monitor})

    return rel


def time_gap(pre, cur):
    pre_after = float(pre.split(".")[1][:-1])
    cur_after = float(cur.split(".")[1][:-1])

    pre_before = pre.split(".")[0]
    cur_before = cur.split(".")[0]

    pre_time = time.mktime(time.strptime(pre_before, '%Y-%m-%dT%H:%M:%S'))
    cur_time = time.mktime(time.strptime(cur_before, '%Y-%m-%dT%H:%M:%S'))

    gap = (cur_time - pre_time) * 1000000000 + cur_after - pre_after

    return gap


def format_size(size):
    if size < 1000:
        return size
    elif size < 1000000:
        return str('%.2f' % (size / 1000)) + 'k'
    elif size < 1000000000:
        return str('%.2f' % (size / 1000000)) + 'm'
    elif size < 1000000000000:
        return str('%.2f' % (size / 1000000000)) + 'g'


def get_networks(username):
    return database_update.get_networks(username)


def get_network(username, network):
    return database_update.get_networks(username, network)


def create_network(username, network):
    client = Client("114.212.189.147:2376", config.c_version).client
    Network.create_network(client, network, 'overlay')
    database_update.create_network(username, network)


def delete_network(username, network):
    client = Client("114.212.189.147:2376", config.c_version).client
    Network.remove_network(client, network)
    database_update.delete_network(username, network)


def get_yaml(username, project_name):
    user_path = config.project_path + "/" + username
    file_dir = OSFS(user_path)
    if file_dir.exists(project_name + "/nap-compose.yml"):
        f = file(config.project_path + "/" + username + "/" + project_name + '/nap-compose.yml')
        return f.read()

    return "yaml"


def get_images(username):
    data = database_update.get_images(username)
    return data


def get_container_ip_port(username, project_name, service_name, container_name):
    ip = database_update.container_ip(username, project_name, service_name, container_name)
    port = database_update.container_port(username, project_name, service_name, container_name)
    client = Client(ip, config.c_version).client
    detail = client.inspect_container(container_name+config.split_mark+project_name+config.split_mark+username)
    host_ports = detail["NetworkSettings"]["Ports"][port][0]["HostPort"]
    return ip.split(":")[0] + ":" + host_port
