# DB Report

<img src="pic/Charts_2.png" style="zoom:25%;" />  数据库自动化报告工具 



## 项目说明

该仓库用于存放混合云数据库管理中常用的数据库报告小工具，持续更新与维护。

## 开发语言和要求

1. Python版本 `>=3.7`
2. 访问阿里云的方式必须包含两种：普通的AK验证方式 和 STS Token验证方式
3. 阿里云的第三方模块使用驻云开发的` zy-aliyun-python-sdk` `>= 0.0.5`
4. 小工具开发必须使用第三方模块 `argparse` 来传递参数

## 工具简介

|文档|说明|
|:--|:--|
|[aliyun_get_rds_slowlog](aliyun_get_rds_slowlog.py)|阿里云RDS实例每日慢查询报告小工具|
|[aliyun_get_polardb_slowlog](aliyun_get_polardb_slowlog.py)|阿里云PolarDB集群每日慢查询报告小工具|
|[aliyun_get_rds_slowlog_send_mail](aliyun_get_rds_slowlog_send_mail.py)|阿里云RDS实例每日慢查询报告小工具，并邮件发送|
|[aliyun_get_polardb_slowlog_send_mail](aliyun_get_polardb_slowlog_send_mail.py)|阿里云PolarDB集群每日慢查询报告小工具，并邮件发送|
|[get_mysql_size_info](get_mysql_size_info.py)|MySQL库表统计报告小工具|
|[get_sqlserver_size_info](get_sqlserver_size_info.py)|SQLServer 库表统计报告小工具|


# 关于我们

<img src="pic/solar.png" style="zoom:25%;" />SuperCloudDBA 我们一直致力于为小伙伴们提供更多的优质技术文档和数据库自动化运维管理工具！
