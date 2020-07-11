# -*- coding: utf-8 -*-
"""
==========================================================================================
请求参数案例1（默认AK传空值为STS Token验证方式，RoleName为空的默认值为ZhuyunFullReadOnlyAccess）:
        'AccessKeyId': None,
        'AccessKeySecret': None,
        'RoleName': None,
请求参数案例2（AK值不为空的时候，为普通的AK验证方式，这时候如果RoleName为非空，STS Token验证方式也不生效）:
        'AccessKeyId': XXXXXXXXXXXXXX,
        'AccessKeySecret': XXXXXXXXXXXXXX,
        'RoleName': None,
请求参数案例3（默认AK传空值为STS Token验证方式，RoleName不为空，RoleName为设置的值）:
        'AccessKeyId': None,
        'AccessKeySecret': None,
        'RoleName': XXXXXXXXXXXXXX,
==========================================================================================
"""
# Build-in Modules
import json
import time
import datetime

# 3rd-part Modules
import argparse
from aliyun_sdk import client
from jinja2 import Template
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

StartTime = (datetime.datetime.now() - datetime.timedelta(hours=24)).strftime("%Y-%m-%dZ")
EndTime = (datetime.datetime.now() - datetime.timedelta(hours=0)).strftime("%Y-%m-%dZ")


class Custom:
    def __init__(self):
        pass

    def get_config(self, **kwargs):
        self.out = kwargs
        self.aliyun = client.AliyunClient(config=kwargs)

    def get_describe_regions(self):
        try:
            status_code, api_res = self.aliyun.common("rds", Action="DescribeRegions")
            region_ids = list(set(map(lambda x: x['RegionId'], api_res['Regions']['RDSRegion']
                                      )))
        except Exception as e:
            print(str(e))
            region_ids = []
        # print(region_ids)
        return region_ids

    def get_instance(self, common_region_ids, db_engines):
        """
        1. 循环所有地域获取所有RDS实例；
        2. 再过滤出指定的数据库类型。
        """
        instance_list = []

        for region_id in common_region_ids:
            page_num = 1
            while True:
                # 循环获取实例
                try:
                    status_code, api_res = self.aliyun.common("rds", Action="DescribeDBInstances", RegionId=region_id,
                                                              PageSize=100,
                                                              PageNumber=page_num)
                except Exception as e:
                    print(str(e))

                if not api_res.get("Items", {}).get("DBInstance", []):
                    break

                # 过滤出指定数据库Engines
                instance_list = instance_list + list(map(
                    lambda x: {"DBInstanceId": x.get("DBInstanceId")},
                    list(filter(lambda x: x["Engine"] in db_engines,
                                api_res.get("Items", {}).get("DBInstance", [])))))
                page_num = page_num + 1
        return instance_list

    def get_instance_attribute(self, **instance_kwargs):
        try:
            status_code, api_res = self.aliyun.common("rds", Action="DescribeDBInstanceAttribute", **instance_kwargs)
            # print(json.dumps(api_res, indent=2))
            api_res = api_res.get("Items", {}).get("DBInstanceAttribute", [])[0]
        except Exception as e:
            print(str(e))
            print("获取RDS实例明细信息")
            api_res = []

        # print(json.dumps(api_res, indent=2))
        return api_res

    def get_describe_slow_logs(self, **kwargs):
        """
        调用该接口时，实例必须为如下版本：

        MySQL所有版本（MySQL 5.7基础版除外）；
        SQL Server 2008 R2；
        MariaDB 10.3。

        获取RDS For MySQL慢查询
        kwargs = {
        "DBInstanceId": "",
        "EndTime":"",
        "StartTime":"",
        "DBName":"",
        "SortKey":""
        }

        """
        try:
            status_code, api_res = self.aliyun.common("rds", Action="DescribeSlowLogs", **kwargs)
        except Exception as e:
            print(str(e))
            print("获取RDS慢查询")
            api_res = {}
        return api_res

    def get_describe_slow_log_records(self, **kwargs):
        """
        https://help.aliyun.com/document_detail/26289.html?spm=a2c4g.11186623.6.1619.5e885d8dTPk0Ae
        调用DescribeSlowLogRecords接口查看实例的慢日志明细。
        :param kwargs:
        kwargs = {
        "DBInstanceId": "",
        "EndTime":"",
        "StartTime":"",
        "DBName":"",
        "SQLHASH":"",
        }
        :return:
        """
        try:
            status_code, api_res = self.aliyun.common("rds", Action="DescribeSlowLogRecords", **kwargs)
        except Exception as e:
            print(str(e))
            print("获取RDS慢查询")
            api_res = {}
        return api_res

    def get_top_10(self, slow_query):
        """
        获取按照执行次数最多，执行时间最长排序的前10条SQL
        order_by_MySQLTotalExecutionCounts_MaxExecutionTime
        :return: list
        """
        if isinstance(slow_query, list) and slow_query:
            items = slow_query[:10]
            """
            list中根据字典的某个key或多个key进行排序，倒
            """
            items.sort(key=lambda x: (x['MySQLTotalExecutionCounts'], x['MaxExecutionTime']), reverse=True)
            return items
        else:
            return []

    def start_up(self, **kwargs):
        # 1.获取实例
        # 1.1 按照地域和数据库引擎过滤实例ID
        instance_list = self.get_instance(kwargs['common_region_ids'], kwargs['db_engines'])
        # 过滤实例ID
        if kwargs['filter_instance']:
            filter_instance_list = list(filter(lambda x: x['DBInstanceId'] in kwargs['DBInstanceIds'], instance_list))
        else:
            filter_instance_list = instance_list
        # print(filter_instance_list)

        # 2 获取慢查询信息
        # 2.1 获取已过滤的实例的慢查询
        params = list(map(
            lambda x:
            {
                "DBInstanceId": x["DBInstanceId"],
                "StartTime": StartTime,
                "EndTime": EndTime,
                "SortKey": "TotalExecutionCounts"
            }, filter_instance_list

        ))
        result = []
        for ins_params in params:
            try:
                response = self.get_describe_slow_logs(**ins_params)["Items"]["SQLSlowLog"]
                sql_list = self.get_top_10(response)
                # print(sql_list)
                # 通过 SQLHASH 获取SQL的执行账号和客户端
                # 'SQLHASH': '18122c83b8203a7028a0e3c92b88bc3a'
                for _sql in sql_list:
                    sql_hash = {
                        "DBInstanceId": ins_params['DBInstanceId'],
                        "EndTime": (datetime.datetime.now() - datetime.timedelta(hours=0)).strftime("%Y-%m-%dT08:00Z"),
                        "StartTime": (datetime.datetime.now() - datetime.timedelta(hours=48)).strftime(
                            "%Y-%m-%dT00:00Z"),
                        "SQLHASH": _sql["SQLHASH"],
                    }
                    # print(json.dumps(sql_hash))
                    hash_response = self.get_describe_slow_log_records(**sql_hash)
                    if hash_response.get('Items', {}).get('SQLSlowRecord', []):
                        _sql['HostAddress'] = hash_response['Items']['SQLSlowRecord'][0]["HostAddress"]
                    else:
                        _sql['HostAddress'] = ''
                        # print(json.dumps(hash_response))
                # 2.2 过滤DBNames
                if kwargs['DBNames']:
                    slow_logs_filter = list(filter(lambda x: x["DBName"] in kwargs['DBNames'], sql_list
                                                   ))
                else:
                    slow_logs_filter = sql_list

                # print(slow_logs_filter)
                slow_log = {
                    "DBInstanceId": ins_params['DBInstanceId'],
                    "sql_list": slow_logs_filter
                }
            except Exception as e:
                print(str(e))
                slow_log = {}
            result.append(slow_log)
        # print(result)

        # 循环所有的实例，打印报告并发送
        for instance_slow_logs in result:
            # print(instance_slow_logs)
            report = GetReport(**instance_slow_logs)
            tbody = report.maker()

            # 发送mail
            kwargs = {
                "to_users": kwargs['to_users'],
                "tbody": tbody,
                "InstanceId": instance_slow_logs["DBInstanceId"],
                "client": "AIA友邦保险",
                "tag": kwargs['tag'],

            }
            send_mail = CloudCareMail(**kwargs)
            send_mail.send_mail()


class GetReport:
    def __init__(self, **kwargs):
        self.render_data = kwargs

    def render_template(self):
        template_data = """    <div class="app-page-title">
        <div class="row col-12">
            <div class="col-md-12">
                <div class="main-card mb-3 card">
                    <div class="card-header"> RDS实例ID：{{ DBInstanceId }} 每日慢SQL TOP 10 明细
                    </div>
                    <div class="table-responsive">
                        <table class="align-middle mb-0 table table-borderless table-striped table-hover">
                            <thead>
                            <tr>
                                <th class="text-center table-title-heading">序号</th>
                                <th class="text-center table-title-heading">实例ID</th>
                                <th class="text-center table-title-heading">数据库</th>
                                <th class="text-center table-title-heading">执行用户和地址</th>
                                <th class="text-center table-title-heading">执行次数</th>
                                <th class="text-center table-title-heading">执行时间</th>
                                <th class="text-center table-title-heading" width="1000">慢查询</th>
                            </tr>
                            </thead>
                                    {% for sql in sql_list %}
                                        <tr>
                                            <td class="text-center table-title-subheading">{{ loop.index }}</td>
                                            <td class="text-center table-title-subheading">{{ DBInstanceId }}</td>
                                            <td class="text-center table-title-subheading">{{ sql.DBName }}</td>
                                            <td class="text-center table-title-subheading">{{ sql.HostAddress }}</td>
                                            <td class="text-center table-title-subheading">{{ sql.MySQLTotalExecutionCounts or sql.SQLServerTotalExecutionCounts }}</td>
                                            <td class="text-center table-title-subheading">{{ sql.MySQLTotalExecutionTimes or sql.SQLServerTotalExecutionTimes }}</td>
                                            <td class="text-center table-title-subheading">{{ sql.SQLText }}</td>
                                        </tr>
                                    {% endfor %}

                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/jquery@3.4.1/dist/jquery.slim.min.js"
            integrity="sha384-J6qa4849blE2+poT4WnyKhv5vZF5SrPo0iEjwBvKU7imGFAV0wwj1yYfoRSJoZ+n"
            crossorigin="anonymous"></script>
        <script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.0/dist/umd/popper.min.js"
            integrity="sha384-Q6E9RHvbIyZFJoft+2mJbHaEWldlvI9IOYy5n3zV9zzTtmI3UksdQRVvoxMfooAo"
            crossorigin="anonymous"></script>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.4.1/dist/js/bootstrap.min.js"
            integrity="sha384-wfSDF2E50Y2D1uUdj0O3uMBJnjuUD4Ih7YwaYd1iqfktj0Uod8GCExl3Og8ifwB6"
            crossorigin="anonymous"></script>
    </div>
</div>
</body>
</html>
"""

        template = Template(template_data)
        return template.render(**self.render_data)

    def maker(self):
        # 因为CSS中存在{{因此不能放在template_data中渲染
        html_string_0 = """<!doctype html>
<html lang="en">
<head>
    <!-- Required meta tags -->
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <!-- Bootstrap CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.4.1/dist/css/bootstrap.min.css"
          integrity="sha384-Vkoo8x4CGsO3+Hhxv8T/Q5PaXtkKtu6ug5TOeNV6gBiFeWPGFN9MuhOf23Q9Ifjh" crossorigin="anonymous">

    <style type="text/css">
        .app-page-title {
            padding-top: 60px;
            flex: 1;
            display: flex;
            z-index: 8;
            position: relative
        }

        .page-title-icon {
            font-size: 2rem;
            display: flex;
            align-items: center;
            align-content: center;
            text-align: center;
            padding: .83333rem;
            margin: 0 30px 0 0;
            background: #fff;
            box-shadow: 0 0.46875rem 2.1875rem rgba(4, 9, 20, 0.03), 0 0.9375rem 1.40625rem rgba(4, 9, 20, 0.03), 0 0.25rem 0.53125rem rgba(4, 9, 20, 0.05), 0 0.125rem 0.1875rem rgba(4, 9, 20, 0.03);
            border-radius: .25rem;
            width: 60px;
            height: 60px
        }

        .page-title-subheading {
            padding: 3px 0 0;
            font-size: .88rem;
            opacity: .6
        }

        .page-title-heading {
            font-size: 1.25rem;
            font-weight: 400;

        }

        .table-title-heading {
            font-size: .5rem;
            opacity: .9
        }

        .table-title-subheading {
            font-size: .5rem;
            opacity: .6
        }

        .card-header {
            padding: 10px 10px 10px;
            font-size: .5rem;
            opacity: .6;
            font-family: verdana;
        }

    </style>
</head>


<body>
<div class="container-fluid">
    <div class="app-page-title">
        <div class="row">
            <div class="col col-2">
                <div class="page-title-icon">
                    <svg t="1584605510076" class="icon" viewBox="0 0 1024 1024" version="1.1"
                         xmlns="http://www.w3.org/2000/svg" p-id="1171" width="200" height="200">
                        <path d="M312.1 591.5c3.1 3.1 8.2 3.1 11.3 0l101.8-101.8 86.1 86.2c3.1 3.1 8.2 3.1 11.3 0l226.3-226.5c3.1-3.1 3.1-8.2 0-11.3l-36.8-36.8c-3.1-3.1-8.2-3.1-11.3 0L517 485.3l-86.1-86.2c-3.1-3.1-8.2-3.1-11.3 0L275.3 543.4c-3.1 3.1-3.1 8.2 0 11.3l36.8 36.8z"
                              p-id="1172"></path>
                        <path d="M904 160H548V96c0-4.4-3.6-8-8-8h-56c-4.4 0-8 3.6-8 8v64H120c-17.7 0-32 14.3-32 32v520c0 17.7 14.3 32 32 32h356.4v32L311.6 884.1c-3.7 2.4-4.7 7.3-2.3 11l30.3 47.2v0.1c2.4 3.7 7.4 4.7 11.1 2.3L512 838.9l161.3 105.8c3.7 2.4 8.7 1.4 11.1-2.3v-0.1l30.3-47.2c2.4-3.7 1.3-8.6-2.3-11L548 776.3V744h356c17.7 0 32-14.3 32-32V192c0-17.7-14.3-32-32-32z m-40 512H160V232h704v440z"
                              p-id="1173"></path>
                    </svg>

                </div>
            </div>
            <div class="col">
                <div class="page-title-heading">
                    阿里云RDS数据库慢日志日报
                    <div class="page-title-subheading">AliYun RDS Slow Log Daily Report
                    </div>
                </div>
            </div>
        </div>
    </div>
        """
        html_string_1 = self.render_template()
        # print('\n'.join([html_string_0, html_string_1]))
        file_name = 'report-{instance}-{time_string}.html'.format(instance=self.render_data['DBInstanceId'],
                                                                  time_string=time.strftime('%Y%m%d%H%M%S',
                                                                                            time.localtime(
                                                                                                time.time())))
        # with open('{}/{}'.format(file_name), 'w') as f:
        #     f.write('\n'.join([html_string_0, html_string_1]))

        return '\n'.join([html_string_0, html_string_1])


class CloudCareMail:
    def __init__(self, **kwargs):
        self.from_user = "operator@jiagouyun.com"
        self.to_users = kwargs['to_users']
        self.host = "smtp.jiagouyun.com"
        self.tbody = kwargs['tbody']
        self.msg = MIMEMultipart('related')
        self.InstanceId = kwargs['InstanceId']
        self.client = Client
        self.tag = kwargs['tag']

    def get_subject(self, ):
        subject = "{0}{1}数据库慢查询Top10_{2}_{3}".format(self.client, self.tag, StartTime, EndTime)
        return subject

    def send_mail(self):
        msgtext = MIMEText(self.tbody, "html", "UTF-8")
        self.msg.attach(msgtext)
        self.msg['Subject'] = self.get_subject()
        self.msg['From'] = self.from_user
        self.msg['To'] = self.to_users
        try:
            server = smtplib.SMTP_SSL(host=self.host)
            server.connect(self.host, port="465")
            server.set_debuglevel(1)
            server.login(self.from_user, "ZYops,./0412")
            server.sendmail(self.from_user, self.to_users, self.msg.as_string())
            server.quit()
            print("发送成功")
        except Exception as e:
            print(str(e))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='''阿里云RDS实例每日慢查询报告小工具，并邮件发送
Example：
获取所有地域RDS实例的每日慢查询报告
    python3 aliyun_get_rds_slowlog.py --RoleName RoleName --DBInstanceId DBInstanceId --DBName dbname1,dbname2 --ToUsers xxx@hotmail.com,xxx@hotmail.com --Tag Test
    python3 aliyun_get_rds_slowlog.py --AccessKeyId ACCESSKEYID --AccessKeySecret ACCESSKEYSECRET --ToUsers xxx@hotmail.com,xxx@hotmail.com --Tag Test
    python3 aliyun_get_rds_slowlog.py --AccessKeyId ACCESSKEYID --AccessKeySecret ACCESSKEYSECRET --Region all --Engine all --ToUsers xxx@hotmail.com,xxx@hotmail.com --Tag Test
    支持指定 地域、存储引擎（MySQL, SQLServer, PostgreSQL, PPAS, MariaDB）、数据库实例ID
获取某实例某库的每日慢查询报告
    python3 aliyun_get_rds_slowlog.py --AccessKeyId ACCESSKEYID --AccessKeySecret ACCESSKEYSECRET --DBInstanceId DBInstanceId --DBName dbname1,dbname2 --ToUsers xxx@hotmail.com,xxx@hotmail.com --Tag Test
''', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--AccessKeyId", help="AccessKeyId 非必要参数")
    parser.add_argument("--AccessKeySecret", help="AccessKeySecret 非必要参数")
    parser.add_argument("--RoleName", help="RoleName 非必要参数")
    parser.add_argument("--OutDir", help="输出目录 必要参数 需要提前创建该目录")
    parser.add_argument("--AccountName", help="用户名 ShowOnly=Yes时为非必要参数")
    parser.add_argument("--AccountPassword", help="密码 ShowOnly=Yes时为非必要参数")
    parser.add_argument("--AccountDescription", help="账号描述 ShowOnly=Yes时为非必要参数")
    parser.add_argument("--Region", default='all', help='''指定地域 默认为all
all : 所有地域
cn-shanghai,cn-hangzhou : 上海和杭州 多个地域使用逗号分割
us-east-1 : 单个地域
因地域经常发化此处不罗列''')
    parser.add_argument("--Engine", default='all', help='''数据库类型 默认为all
    all : 所有数据库类型
    MySQL,SQLServer : 多个类型用逗号分割
    PostgreSQL : 单个类型
    支持的所有类型：MySQL, SQLServer, PostgreSQL, PPAS, MariaDB''')
    parser.add_argument("--DBInstanceId", default='all', help='''数据库实例ID 默认为all
    rr-bp1d96998y68h5439,rm-bp1l20jmw5p587zl2 : 多个实例用逗号分割
    rr-bp1d96998y68h5439 : 单个实例''')
    parser.add_argument("--DBName", help='''数据库名 非必要参数，如果指定必须与 --DBInstanceId 单实例 同时使用
    db1,db2 : 多个库
    db1 : 单个库''')
    parser.add_argument("--ToUsers", help='邮件接收者必要参数 a@hotmail.com,b@hotmail.com')
    parser.add_argument("--Tag", help='Tag')
    parser.add_argument("--Client", default='我的公司', help='指定公司名称，作为邮件标题的前缀，默认为 我的公司')

    args = parser.parse_args()

    common_region_ids = []
    db_engines = []

    if args.ToUsers:
        Client = args.Client
        params = {
            'AccessKeyId': args.AccessKeyId,
            'AccessKeySecret': args.AccessKeySecret,
            'RoleName': args.RoleName,
        }
        api = Custom()
        api.get_config(**params)

        if args.Region == 'all':
            common_region_ids = api.get_describe_regions()
        elif len(args.Region.split(',')):
            common_region_ids = args.Region.split(',')

        if args.Engine == 'all':
            db_engines = ['MySQL', 'SQLServer', 'PostgreSQL', 'PPAS', 'MariaDB']
        elif len(args.Engine.split(',')):
            db_engines = args.Engine.split(',')

        if args.DBName and (len(args.DBInstanceId.split(',')) > 1 or args.DBInstanceId == 'all'):
            print('数据库名 非必要参数，如果指定必须与 --DBInstanceId 单实例 同时使用')
            exit()
        else:
            db_names = args.DBName.split(',') if args.DBName else []

        main_kwargs = {
            'common_region_ids': common_region_ids,
            'db_engines': db_engines,
            'filter_instance': False if args.DBInstanceId == 'all' else True,
            'DBInstanceIds': args.DBInstanceId.split(','),
            'DBNames': db_names,
            'to_users': args.ToUsers,
            'tag': args.Tag,
        }
        api.start_up(**main_kwargs)
