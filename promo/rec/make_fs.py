#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a believable Kylin user machine for the QianXun demo.
Re-runnable: wipes /home/kylin and /data, regenerates (deterministic RNG).
Empty / sparse files only. Usage: python3 make_fs.py [scale]"""
import os, sys, time, random, datetime, subprocess, math

SCALE = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
R = random.Random(20261017)
NOW = time.time()
TODAY0 = time.mktime(datetime.date.today().timetuple())
T = lambda y, m, d, H=10, M=0, S=0: time.mktime((y, m, d, H, M, S, 0, 0, -1))
MB, GB = 1 << 20, 1 << 30

HOME = '/home/kylin'
DATA = '/data'
dirs_made = set()
dir_mt = {}
nfiles = 0


def mkdir(p):
    if p in dirs_made:
        return
    os.makedirs(p, exist_ok=True)
    q = p
    while q not in dirs_made and q not in ('/', HOME, DATA):
        dirs_made.add(q)
        q = os.path.dirname(q)


LO, HI = T(2021, 3, 1), T(2026, 10, 15)


def rand_mt(lo=LO, hi=HI):
    u = R.random() ** 0.7
    return lo + (hi - lo) * u


def put(path, size=0, mt=None, today=False):
    global nfiles
    d = os.path.dirname(path)
    if d not in dirs_made:
        mkdir(d)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    if size:
        os.ftruncate(fd, size)
    os.close(fd)
    if mt is None:
        mt = rand_mt()
    if mt > T(2026, 10, 16, 0) and not today:
        mt = T(2026, 10, R.randint(1, 15), R.randint(7, 22), R.randint(0, 59))
    os.utime(path, (mt, mt))
    if dir_mt.get(d, 0) < mt:
        dir_mt[d] = mt
    nfiles += 1


def dt_mt(y, m, d, H=None):
    H = R.randint(7, 22) if H is None else H
    return T(y, m, d, H, R.randint(0, 59), R.randint(0, 59))


SIZES = {
    'docx': (18e3, 6e6), 'doc': (30e3, 3e6), 'wps': (20e3, 4e6), 'xlsx': (12e3, 3e6), 'et': (12e3, 2e6),
    'pptx': (200e3, 40e6), 'dps': (200e3, 30e6), 'pdf': (80e3, 30e6), 'txt': (200, 80e3), 'md': (300, 40e3),
    'jpg': (1.2e6, 9e6), 'JPG': (3e6, 9e6), 'png': (60e3, 3e6), 'mp4': (20e6, 90e6), 'MP4': (60e6, 95e6), 'mp3': (2.5e6, 11e6),
    'c': (400, 60e3), 'h': (200, 20e3), 'cpp': (500, 80e3), 'py': (200, 40e3), 'o': (2e3, 200e3), 'json': (100, 200e3),
    'log': (1e3, 8e6), 'gz': (2e3, 900e3), 'csv': (2e3, 30e6), 'bin': (10e3, 90e6), 'tlog': (100e3, 20e6),
    'zip': (1e6, 90e6), 'js': (300, 90e3), 'deb': (2e6, 90e6), 'pyc': (1e3, 60e3),
}


def rsize(ext):
    lo, hi = SIZES.get(ext, SIZES.get(ext.lower(), (500, 200e3)))
    return int(math.exp(R.uniform(math.log(lo), math.log(hi))))


def wipe():
    for p in (HOME, DATA):
        if os.path.exists(p):
            subprocess.call(['rm', '-rf', p])
    os.makedirs(HOME, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)


TOPICS = ['门户网站', '协同办公', '档案数字化', '报表平台', '行政后勤', '人事招聘', '财务报销', '资产管理', '采购管理', '合同管理',
          '客户服务', '市场推广', '质量管理', '安全生产', '设备维护', '会议服务', '员工培训', '品牌宣传', '供应商管理', '库存管理',
          '车辆管理', '节能改造', '机房建设', '网络改造', '电子签章', '移动办公', '知识库', '数据治理']
DOCTYPES = ['需求规格说明书', '设计说明书', '技术协议', '接口控制文件', '测试大纲', '测试细则', '会议纪要', '评审意见',
            '工作计划', '预算表', '进度表', '合同', '合同扫描件', '采购清单', '用户手册', '维护手册', '配置管理计划',
            '质量管理制度', '风险清单', '问题清单', '周报', '月报', '状态记录', '软件说明', '项目任务书', '实施细则',
            '验证方案', '实施方案', '技术方案', '保障方案', '工作总结', '培训材料', '操作规程']
VERS = ['v1', 'v2', 'v3', 'v1.1', 'v2.0', '终版', '定稿', '评审版', '修订版', '送审稿', '0915', '0328', '1127', '正式版']
DEXT = ['docx'] * 7 + ['wps'] * 2 + ['pdf'] * 5 + ['xlsx'] * 3 + ['et'] + ['pptx'] * 2 + ['doc', 'txt', 'md']
PHASES = ['01_方案论证', '02_设计开发', '03_测试验证', '04_评审', '05_实施', '06_交付', '07_保障', '08_其他']
PEOPLE = ['张', '王', '李', '刘', '陈', '杨', '赵', '黄', '周', '吴', '郭', '孙']


def doc_name():
    t = R.choice(TOPICS)
    d = R.choice(DOCTYPES)
    ext = R.choice(DEXT)
    v = R.choice(VERS) if R.random() < 0.6 else ''
    form = R.random()
    if R.random() < 0.0012:
        d = R.choice(['测试报告', '验收报告', '调研报告', '分析报告', '技术报告'])
        if R.random() < 0.3:
            v = R.choice(['2024', '2024Q2', '2024年', '2024-11'])
        if R.random() < 0.15:
            v = '草稿'
    if form < 0.55:
        n = '%s%s' % (t, d)
    elif form < 0.8:
        n = '%s_%s' % (t, d)
    else:
        n = '%s%s' % (d, R.choice(['', '（%s工）' % R.choice(PEOPLE)]))
    if v:
        n += '_' + v
    elif R.random() < 0.1:
        n += '_草稿'
    return n + '.' + ext, ext


def showcase():
    H, D = HOME, DATA
    P = H + '/文档/项目方案/'

    def f(path, size=None, mt=None, today=False):
        e = path.rsplit('.', 1)[-1]
        put(path, rsize(e) if size is None else size, mt, today)

    items = [
        (P + '总体方案_v1.docx', T(2025, 2, 11, 14, 22)), (P + '总体方案_v2.docx', T(2025, 3, 6, 9, 41)),
        (P + '总体方案_v3.docx', T(2025, 4, 18, 16, 5)), (P + '总体方案_v3_草稿.docx', T(2025, 4, 9, 11, 30)),
        (P + '总体方案_v3.pdf', T(2025, 4, 19, 10, 12)), (P + '总体方案_评审意见.pdf', T(2025, 4, 25, 15, 48)),
        (P + '总体方案汇报.pptx', T(2025, 4, 21, 8, 55)), (P + '门户网站改版总体方案.wps', T(2024, 11, 3, 20, 14)),
        (P + '门户网站改版总体方案.pdf', T(2024, 11, 5, 9, 20)), (P + '协同办公平台总体方案_v2.docx', T(2024, 7, 22, 13, 31)),
        (P + '协同办公平台总体方案（草稿）.docx', T(2024, 6, 14, 17, 2)), (P + '档案数字化总体方案_终版.pdf', T(2025, 9, 2, 10, 40)),
        (P + '档案数字化总体方案_v1.docx', T(2025, 7, 28, 19, 6)), (H + '/桌面/总体方案_最新.docx', T(2026, 9, 28, 17, 33)),
        (H + '/下载/总体方案_v3_修订.docx', T(2026, 8, 3, 9, 12)), (H + '/下载/总体方案模板.dotx', T(2023, 5, 17, 10, 0)),
        (H + '/下载/总体方案_批注版.pdf', T(2026, 8, 5, 21, 47)), (H + '/工作区/office-portal/docs/总体方案_接口说明.md', T(2026, 3, 12, 15, 20)),
        (D + '/项目归档/2023/P-2301_门户网站/01_方案论证/总体方案_v1.docx', T(2023, 3, 15, 10, 8)),
        (D + '/项目归档/2023/P-2301_门户网站/01_方案论证/总体方案_v2.docx', T(2023, 4, 20, 14, 36)),
        (D + '/项目归档/2023/P-2301_门户网站/01_方案论证/总体方案_评审纪要.pdf', T(2023, 5, 8, 16, 11)),
        (D + '/项目归档/2023/P-2301_门户网站/01_方案论证/总体方案草稿_0612.docx', T(2023, 6, 12, 18, 25)),
        (D + '/项目归档/2024/P-2402_协同办公/01_方案论证/总体方案_v1.docx', T(2024, 2, 26, 11, 3)),
        (D + '/项目归档/2024/P-2402_协同办公/01_方案论证/总体方案_v2.docx', T(2024, 3, 29, 15, 50)),
        (D + '/项目归档/2024/P-2402_协同办公/01_方案论证/总体方案_v2.pdf', T(2024, 3, 30, 9, 9)),
        (D + '/项目归档/2024/P-2402_协同办公/04_评审/总体方案评审意见汇总.xlsx', T(2024, 4, 12, 13, 27)),
        (D + '/项目归档/2025/P-2503_档案数字化/01_方案论证/总体方案_v1.docx', T(2025, 5, 14, 10, 44)),
        (D + '/项目归档/2025/P-2503_档案数字化/01_方案论证/总体方案_v2.docx', T(2025, 6, 9, 16, 19)),
        (D + '/项目归档/2025/P-2503_档案数字化/01_方案论证/总体方案（草稿）.docx', T(2025, 5, 2, 20, 1)),
        (D + '/备份/2025-12-31/文档/项目方案/总体方案_v3.docx', T(2025, 4, 18, 16, 5)),
        (D + '/资料库/参考案例/总体方案/行业信息化总体方案_公开版.pdf', T(2022, 9, 9, 9, 9)),
        (D + '/资料库/参考案例/总体方案/总体方案编写指南.pdf', T(2022, 9, 9, 9, 30)),
    ]
    for p, mt in items:
        f(p, mt=mt)

    Q = H + '/文档/汇报/'
    for p, mt in [
        (Q + '第一季度汇报.pptx', T(2026, 4, 7, 9, 30)), (Q + '第二季度汇报.pptx', T(2026, 7, 6, 10, 15)),
        (Q + '第三季度汇报.pptx', T(2026, 10, 8, 10, 15)), (Q + '第三季度汇报_草稿.docx', T(2026, 10, 9, 18, 2)),
        (Q + '季度汇报_草稿.docx', T(2026, 10, 12, 16, 40)), (Q + '季度汇报模板.potx', T(2024, 1, 15, 10, 0)),
        (Q + '2025年第四季度汇报.pptx', T(2026, 1, 8, 14, 22)),
        (D + '/项目归档/2025/P-2503_档案数字化/06_交付/第二季度汇报_v2.pptx', T(2025, 7, 4, 15, 0)),
        (Q + '年终汇报.pptx', T(2025, 12, 26, 9, 0)), (Q + '周例会汇报_0915.pptx', T(2026, 9, 15, 8, 40)),
        (Q + '项目进展汇报_2024Q3.pptx', T(2024, 10, 11, 10, 5)), (Q + '汇报材料_终版.docx', T(2025, 3, 3, 17, 20)),
        (Q + '专项汇报提纲.docx', T(2025, 8, 19, 11, 11)), (Q + '领导调研汇报.pptx', T(2024, 5, 28, 16, 26)),
        (Q + '汇报视频脚本.txt', T(2025, 11, 2, 21, 5)), (P + '现场调研汇报_v2.pptx', T(2025, 10, 14, 9, 50)),
        (D + '/项目归档/2024/P-2402_协同办公/04_评审/评审汇报_0412.pptx', T(2024, 4, 12, 8, 30)),
        (D + '/项目归档/2023/P-2301_门户网站/04_评审/节点汇报.pptx', T(2023, 8, 17, 14, 14)),
        (D + '/项目归档/2023/P-2301_门户网站/06_交付/验收汇报.pptx', T(2023, 12, 19, 9, 45)),
        (D + '/项目归档/2025/P-2503_档案数字化/04_评审/中期汇报.pptx', T(2025, 8, 21, 10, 0)),
        (H + '/下载/培训汇报_模板.pptx', T(2026, 6, 1, 10, 0)),
    ]:
        f(p, mt=mt)

    for p, mt in [
        (H + '/文档/报告/2024年度测试报告_门户.pdf', T(2024, 12, 20, 10, 10)), (H + '/文档/报告/2024Q3_测试报告.docx', T(2024, 10, 8, 16, 45)),
        (H + '/文档/报告/现场实施报告_2024.docx', T(2024, 9, 18, 13, 0)), (H + '/文档/报告/2024年度工作进展报告.docx', T(2025, 1, 6, 9, 30)),
        (H + '/文档/报告/调研报告_2024-06.docx', T(2024, 6, 27, 18, 5)), (H + '/文档/报告/2024年验收报告.pdf', T(2024, 12, 30, 15, 15)),
        (H + '/文档/报告/技术状态报告_2024.xlsx', T(2024, 8, 2, 11, 40)), (H + '/文档/报告/2024年第二季度进展报告.pptx', T(2024, 7, 3, 9, 8)),
        (H + '/文档/报告/2024年度质量分析报告.docx', T(2025, 1, 14, 17, 2)), (H + '/文档/报告/报告_2024年9月.docx', T(2024, 9, 30, 20, 1)),
        (H + '/文档/报告/2024年总结报告（草稿）.docx', T(2024, 12, 11, 14, 14)), (H + '/文档/报告/报告初稿2024_草稿.docx', T(2024, 12, 2, 10, 20)),
        (H + '/文档/报告/系统可用性分析报告_2023.pdf', T(2023, 11, 8, 10, 0)), (H + '/文档/报告/测试报告_模板.docx', T(2023, 2, 1, 10, 0)),
        (D + '/项目归档/2024/P-2402_协同办公/03_测试验证/协同办公平台测试报告_2024.pdf', T(2024, 9, 5, 14, 30)),
        (D + '/项目归档/2024/P-2402_协同办公/06_交付/验收报告_2024.pdf', T(2024, 12, 25, 11, 0)),
        (D + '/项目归档/2024/P-2402_协同办公/03_测试验证/联调测试报告_2024-08.docx', T(2024, 8, 29, 18, 35)),
        (D + '/项目归档/2024/P-2402_协同办公/03_测试验证/联调测试报告_2024-08（草稿）.docx', T(2024, 8, 20, 9, 5)),
        (D + '/项目归档/2023/P-2301_门户网站/03_测试验证/上线试运行报告.pdf', T(2023, 10, 12, 10, 10)),
        (D + '/资料库/技术手册/2024行业调研报告.pdf', T(2024, 3, 15, 9, 0)),
    ]:
        f(p, mt=mt)

    for p, mt in [
        (H + '/文档/项目方案/技术协议.wps', T(2025, 1, 20, 14, 0)), (H + '/文档/项目方案/技术协议_终版.docx', T(2025, 2, 3, 10, 0)),
        (H + '/文档/工作总结/2024年度工作总结.docx', T(2025, 1, 10, 16, 0)), (H + '/文档/工作总结/2025年度工作总结.docx', T(2026, 1, 9, 15, 30)),
        (H + '/文档/工作总结/2023年度工作总结.docx', T(2024, 1, 12, 15, 0)), (H + '/文档/项目方案/需求规格说明书.pdf', T(2025, 3, 1, 9, 0)),
        (H + '/文档/会议纪要/会议纪要_0915.docx', T(2026, 9, 15, 17, 40)), (H + '/文档/会议纪要/会议纪要_0828.docx', T(2026, 8, 28, 17, 10)),
        (H + '/文档/合同/合同扫描件.pdf', T(2025, 6, 6, 11, 11)), (H + '/文档/合同/外协合同_2025.pdf', T(2025, 3, 21, 10, 5)),
        (H + '/文档/预算/预算表.et', T(2025, 12, 1, 9, 0)), (H + '/文档/预算/预算表.xlsx', T(2025, 12, 2, 9, 30)),
        (H + '/文档/预算/2026年度预算表.xlsx', T(2026, 2, 12, 15, 0)),
    ]:
        f(p, mt=mt)

    td = [
        (H + '/文档/项目方案/评审意见汇总_0917.docx', 8, 12), (H + '/文档/会议纪要/会议纪要_1017.docx', 9, 40),
        (H + '/文档/预算/经费测算草表.xlsx', 10, 5), (H + '/桌面/待办事项.txt', 11, 22),
        (H + '/下载/P-2603_任务书.pdf', 13, 48), (H + '/工作区/office-portal/src/api/router.c', 14, 31),
        (H + '/工作区/office-portal/docs/CHANGELOG.md', 15, 2),
        (D + '/项目归档/2026/P-2603_报表平台/01_方案论证/报表设计说明_v1.docx', 16, 20),
        (D + '/项目归档/2026/P-2603_报表平台/02_设计开发/接口控制文件_草稿.docx', 17, 45),
        (H + '/图片/2026/10/IMG_20261017_183021.jpg', 18, 30), (H + '/文档/周报/周报_第42周.docx', 19, 10),
        (H + '/视频/活动记录/DJI_0412.MP4', 20, 5),
    ]
    for p, h, m in td:
        mt = max(min(T(2026, 10, 17, h, m), NOW - 1800), TODAY0 + 60)
        f(p, mt=mt, today=True)

    big = [
        (H + '/视频/活动记录/DJI_0231.MP4', 1.8 * GB), (H + '/视频/活动记录/DJI_0232.MP4', 2.4 * GB),
        (H + '/视频/活动记录/DJI_0233.MP4', 3.1 * GB), (H + '/视频/活动记录/DJI_0234.MP4', 1.2 * GB),
        (H + '/视频/2025年年会/年会全程记录_1080p.mp4', 6.8 * GB), (H + '/视频/2025年年会/颁奖环节_慢动作.mp4', 940 * MB),
        (H + '/视频/培训录像/新员工培训_第一讲.mp4', 1.1 * GB), (H + '/视频/培训录像/新员工培训_第二讲.mp4', 1.3 * GB),
        (H + '/视频/家庭/20250201_春节.mp4', 780 * MB), (H + '/视频/成片/项目宣传片_终版.mp4', 1.6 * GB),
        (H + '/下载/Kylin-Desktop-V10-SP1-2403-x86_64.iso', 4.3 * GB), (H + '/下载/Kylin-Desktop-V10-SP1-Phytium-arm64.iso', 4.1 * GB),
        (H + '/下载/ubuntu-24.04.1-desktop-amd64.iso', 5.9 * GB), (H + '/下载/qt-opensource-linux-x64-5.15.2.run', 480 * MB),
        (H + '/下载/matlab_R2023b_glnxa64.zip', 2.9 * GB), (H + '/工作区/vm/kylin-test.qcow2', 18 * GB),
        (H + '/工作区/vm/win10-sim.vdi', 24 * GB), (D + '/备份/家目录/home_kylin_2026-09-30.tar.zst', 38 * GB),
        (D + '/备份/家目录/home_kylin_2026-06-30.tar.zst', 34 * GB), (D + '/备份/家目录/home_kylin_2026-03-31.tar.zst', 31 * GB),
        (D + '/备份/数据库/pg_dump_2026-10-01.sql.gz', 2.6 * GB), (D + '/备份/数据库/pg_dump_2026-09-01.sql.gz', 2.5 * GB),
        (D + '/资料库/活动影像/20260816_年会/全程视频.mp4', 9.4 * GB), (D + '/资料库/活动影像/20260816_年会/会场直播回放.mkv', 7.2 * GB),
        (D + '/资料库/活动影像/20250920_团建/合影原片.MP4', 5.1 * GB), (D + '/资料库/活动影像/20250920_团建/花絮录像.mp4', 3.3 * GB),
        (D + '/项目归档/2025/P-2503_档案数字化/05_实施/系统演示录屏.mp4', 410 * MB),
        (D + '/项目归档/2024/P-2402_协同办公/05_实施/培训视频汇总.mp4', 2.0 * GB),
        (D + '/项目归档/2023/P-2301_门户网站/05_实施/上线直播录像.mp4', 1.5 * GB),
        (D + '/资料库/软件安装包/WPS-Office-11.1.0-amd64.deb', 256 * MB), (D + '/资料库/软件安装包/dataset_ocr_v2.tar', 12 * GB),
        (H + '/视频/活动记录/DJI_0412.MP4', 2.2 * GB),
    ]
    for p, sz in big:
        mt = dt_mt(R.choice([2024, 2025, 2026]), R.randint(1, 9), R.randint(1, 28))
        if os.path.exists(p):
            mt = os.stat(p).st_mtime
        put(p, int(sz), mt)


def gen_photos(total):
    n = 0
    years = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
    per_month = max(1, int(total / (len(years) * 12)))
    seen = set()
    for y in years:
        for m in range(1, 13):
            if y == 2026 and m > 10:
                break
            base = '%s/图片/%d/%02d/' % (HOME, y, m) if y >= 2024 else '%s/资料库/照片/%d/%02d/' % (DATA, y, m)
            for _ in range(per_month):
                d = R.randint(1, 28)
                H, M, S = R.randint(6, 21), R.randint(0, 59), R.randint(0, 59)
                r = R.random()
                if r < 0.78:
                    nm = 'IMG_%d%02d%02d_%02d%02d%02d.jpg' % (y, m, d, H, M, S)
                elif r < 0.86:
                    nm = 'DJI_%04d.JPG' % R.randint(1, 9999)
                elif r < 0.93:
                    nm = 'Screenshot_%d-%02d-%02d_%02d-%02d-%02d.png' % (y, m, d, H, M, S)
                elif r < 0.97:
                    nm = '微信图片_%d%02d%02d%02d%02d%02d.jpg' % (y, m, d, H, M, S)
                else:
                    nm = '截图 %d-%02d-%02d %02d-%02d-%02d.png' % (y, m, d, H, M, S)
                if base + nm in seen:
                    continue
                seen.add(base + nm)
                put(base + nm, rsize(nm.rsplit('.', 1)[-1]), T(y, m, d, H, M, S))
                n += 1
    put(HOME + '/图片/2024/05/IMG_20240512_093012.jpg', 4812345, T(2024, 5, 12, 9, 30, 12))
    return n


REPOS = ['office-portal', 'oa-workflow', 'hr-system', 'mail-gateway', 'meeting-booking', 'qt-hmi', 'report-engine',
         'printer-driver', 'search-filter', 'metrics-svc', 'sync-proto', 'ldap-bridge', 'api-gateway', 'video-stream',
         'issue-tracker', 'schedule-planner', 'param-tool', 'log-analyzer', 'erp-adapter', 'rtos-bsp', 'board-support-arm64',
         'crypto-lib', 'config-center', 'web-dashboard', 'edge-agent', 'time-sync', 'data-fusion', 'ota-updater',
         'test-harness', 'load-bench', 'map-tiles', 'net-monitor', 'audit-replay', 'form-codegen', 'kylin-pkg',
         'serial-tool', 'proto-defs', 'asset-manager', 'power-ctrl', 'kiosk-ctrl']
MODS = ['core', 'api', 'auth', 'db', 'drv', 'net', 'ui', 'util', 'proto', 'sched', 'cache', 'cfg', 'log', 'fs', 'crypto', 'time']
SUBM = ['init', 'main', 'state', 'event', 'queue', 'parser', 'codec', 'filter', 'route', 'timer', 'buffer', 'crc', 'mem',
        'task', 'msg', 'uart', 'spi', 'can', 'pwm', 'adc', 'json', 'http', 'plan', 'sql', 'cache', 'conn', 'session', 'store']


def gen_repo(base, target, node=False):
    n = 0
    y = R.choice([2022, 2023, 2024, 2025, 2026])
    lo = T(y, 1, 1)
    hi = min(NOW - 86400, lo + 2.2 * 365 * 86400)
    mk = lambda: rand_mt(lo, hi)
    for f in ('README.md', 'LICENSE', 'CMakeLists.txt', '.gitignore', 'Makefile', 'setup.py'):
        put(base + '/' + f, rsize('md'), mk()); n += 1
    for i in range(R.randint(8, 18)):
        put('%s/.git/objects/%02x/%038x' % (base, i * 7 % 256, R.getrandbits(150)), rsize('json'), mk()); n += 1
    for f in ('HEAD', 'config', 'index'):
        put('%s/.git/%s' % (base, f), 300, mk()); n += 1
    if node:
        while n < target:
            pkg = 'node_modules/%s-%s' % (R.choice(['lodash', 'react', 'vue', 'axios', 'echarts', 'webpack', 'babel', 'core-js', 'moment', 'chalk', 'debug', 'ms', 'qs', 'uuid', 'yargs']), R.getrandbits(20))
            for sub in ('', 'lib/', 'dist/', 'src/', 'lib/utils/'):
                for k in range(R.randint(2, 7)):
                    put('%s/%s/%s%s.js' % (base, pkg, sub, R.choice(SUBM) + str(k)), rsize('js'), mk()); n += 1
            for f in ('package.json', 'README.md', 'LICENSE', 'index.js'):
                put('%s/%s/%s' % (base, pkg, f), rsize('json'), mk()); n += 1
        return n
    mods = R.sample(MODS, R.randint(6, 12))
    subs = R.sample(SUBM, 10)
    while n < target:
        mod = R.choice(mods)
        sm = R.choice(SUBM)
        lang = R.choice(['c', 'c', 'c', 'cpp', 'py', 'py'])
        sd = R.choice(['src/%s/' % mod, 'src/%s/%s/' % (mod, R.choice(subs)), 'src/%s/impl/' % mod])
        nm = '%s_%s' % (sm, R.choice(SUBM))
        put('%s/%s%s.%s' % (base, sd, nm, lang), rsize(lang), mk()); n += 1
        if lang != 'py':
            put('%s/include/%s/%s.h' % (base, mod, nm), rsize('h'), mk()); n += 1
            if R.random() < 0.8:
                put('%s/build/CMakeFiles/%s.dir/%s%s.%s.o' % (base, mod, sd.replace('/', '_'), nm, lang), rsize('o'), mk()); n += 1
        else:
            put('%s/%s__pycache__/%s.cpython-313.pyc' % (base, sd, nm), rsize('pyc'), mk()); n += 1
        if R.random() < 0.35:
            put('%s/tests/%s/test_%s.%s' % (base, mod, nm, 'py' if lang == 'py' else 'c'), rsize('c'), mk()); n += 1
        if R.random() < 0.05:
            put('%s/docs/%s_设计说明.md' % (base, mod), rsize('md'), mk()); n += 1
        if R.random() < 0.04:
            put('%s/third_party/%s/%s.%s' % (base, R.choice(['zlib', 'mbedtls', 'cjson', 'protobuf-c', 'libuv']), nm, R.choice(['c', 'h'])), rsize('c'), mk()); n += 1
    return n


def gen_logs(total):
    hosts = ['oa-gw01', 'oa-gw02', 'file-srv', 'web-node1', 'web-node2', 'edge-box3']
    per = total // (len(hosts) * 34)
    n = 0
    for h in hosts:
        for k in range(34):
            y = 2024 + (k + 2) // 12
            m = (k + 2) % 12 + 1
            if (y, m) > (2026, 10):
                continue
            base = '%s/备份/服务日志/%s/%d/%02d/' % (DATA, h, y, m)
            for i in range(per):
                d = (i // 24) % 28 + 1
                hh = i % 24
                kind = R.random()
                if kind < 0.7:
                    nm = '%s-%d%02d%02d-%02d.log.gz' % (h.split('-')[0], y, m, d, hh)
                elif kind < 0.9:
                    nm = 'access-%d%02d%02d-%02d.log' % (y, m, d, hh)
                else:
                    nm = 'error-%d%02d%02d-%02d.txt' % (y, m, d, hh)
                put(base + nm, rsize(nm.rsplit('.', 1)[-1]), T(y, m, d, hh, R.randint(0, 59)))
                n += 1
    return n


def gen_datasets(total):
    n = 0
    sessions = max(60, total // 120)
    for s in range(sessions):
        y = R.choice([2023, 2024, 2025, 2026])
        m = R.randint(1, 12)
        if (y, m) > (2026, 10):
            m = 9
        d = R.randint(1, 28)
        place = R.choice(['总部', '分部', '库房', '展厅', '园区', '门店'])
        base = '%s/资料库/采集数据/%d%02d%02d_%s%d/' % (DATA, y, m, d, place, s)
        for i in range(total // sessions):
            r = R.random()
            if r < 0.4:
                nm = 'record_%05d.csv' % i
            elif r < 0.7:
                nm = 'data_%05d.bin' % i
            elif r < 0.85:
                nm = '%d-%02d-%02d %02d-%02d-%02d.log' % (y, m, d, R.randint(8, 17), R.randint(0, 59), R.randint(0, 59))
            else:
                nm = 'cam%d_%05d.json' % (R.randint(0, 3), i)
            put(base + nm, rsize(nm.rsplit('.', 1)[-1]), T(y, m, d, R.randint(8, 17), R.randint(0, 59)))
            n += 1
    return n


def gen_projects(total):
    n = 0
    projs = []
    for y in range(2019, 2027):
        for k in range(R.randint(6, 10)):
            projs.append((y, 'P-%02d%02d_%s' % (y % 100, k + 5, R.choice(TOPICS))))
    per = total // len(projs)
    for y, pj in projs:
        base = '%s/项目归档/%d/%s/' % (DATA, y, pj)
        for i in range(per):
            ph = R.choice(PHASES)
            sub = R.choice(['', '', '', '历史版本/', '输入/', '输出/', '参考/'])
            nm, ext = doc_name()
            put(base + ph + '/' + sub + nm, rsize(ext), rand_mt(T(y, 1, 1), min(NOW - 86400, T(y + 2, 12, 31))))
            n += 1
    return n


def gen_library(total):
    n = 0
    std = ['GB', 'GB_T', 'ISO', 'ISO_IEC', 'IEEE_Std', 'IEC', 'DB11', 'YD_T']
    cats = {'标准规范': 0.35, '论文文献': 0.4, '技术手册': 0.15, '参考资料': 0.1}
    for cat, share in cats.items():
        for i in range(int(total * share)):
            if cat == '标准规范':
                nm = '%s_%d-%d_%s.pdf' % (R.choice(std), R.randint(100, 9999), R.randint(1998, 2024), R.choice(TOPICS) + R.choice(['要求', '通用规范', '实施指南', '术语']))
            elif cat == '论文文献':
                nm = '%s_%s_%d.pdf' % (R.choice(['基于深度学习的', '面向中小企业的', '多部门协同', '一种改进的', 'A_Survey_on', 'Towards']), R.choice(TOPICS), R.randint(2016, 2026))
            elif cat == '技术手册':
                nm = '%s_%s用户手册_V%d.%d.pdf' % (R.choice(['Phytium', 'Jetson', 'RK3588', 'Hikvision', '联想', '惠普', '华为']), R.choice(['开发板', '打印机', '路由器', '交换机', '投影仪']), R.randint(1, 5), R.randint(0, 9))
            else:
                nm = '%s_%s.%s' % (R.choice(['参考', '资料', '笔记', '摘录']), R.choice(TOPICS) + str(R.randint(1, 400)), R.choice(['pdf', 'docx', 'md', 'txt']))
            ext = nm.rsplit('.', 1)[-1]
            put('%s/资料库/%s/%s/%s' % (DATA, cat, R.choice(TOPICS), nm), rsize(ext), rand_mt(T(2019, 1, 1), HI)); n += 1
    return n


def gen_home_misc():
    n = 0
    for sect, cnt in (('项目方案', 400), ('会议纪要', 500), ('周报', 120), ('合同', 90), ('预算', 80), ('工作总结', 40), ('报告', 100), ('培训', 300), ('标准', 400)):
        for i in range(cnt):
            nm, ext = doc_name()
            if sect == '周报':
                nm, ext = '周报_第%d周%s.docx' % (R.randint(1, 52), R.choice(['', '_张', '_修订'])), 'docx'
            if sect == '会议纪要':
                nm, ext = '会议纪要_%02d%02d%s.docx' % (R.randint(1, 12), R.randint(1, 28), R.choice(['', '', '_终版', '_v2'])), 'docx'
            put('%s/文档/%s/%s/%s' % (HOME, sect, R.choice(['2023', '2024', '2025', '2026']), nm), rsize(ext), rand_mt()); n += 1
    arts = ['周杰伦', '陈奕迅', '邓丽君', '久石让', 'Coldplay', 'Adele', '许巍', '朴树', '五月天', 'Ludovico Einaudi']
    for a in arts:
        for al in range(R.randint(4, 8)):
            for tr in range(R.randint(8, 14)):
                put('%s/音乐/%s/专辑%d/%02d_%s.mp3' % (HOME, a, al + 1, tr + 1, R.choice(['晴天', '夜曲', '稻香', 'Yellow', 'Hello', '蓝莲花', 'Summer', 'Nuvole', '平凡之路', '海阔天空', '光年之外', '青花瓷']) + str(R.randint(1, 99))), rsize('mp3'), rand_mt(T(2021, 1, 1), HI)); n += 1
    for i in range(1800):
        e = R.choice(['pdf', 'zip', 'deb', 'docx', 'png', 'jpg', 'xlsx', 'txt'])
        nm = R.choice(['download', 'file', '附件', '新建文档', 'setup', 'export', '资料包', 'screenshot', '未命名']) + '(%d).%s' % (R.randint(1, 500), e)
        put('%s/下载/%s' % (HOME, nm), rsize(e), rand_mt(T(2023, 1, 1), HI)); n += 1
    for i in range(300):
        put('%s/视频/%s/VID_%d%02d%02d_%06d.mp4' % (HOME, R.choice(['活动记录', '2025年年会', '培训录像', '家庭', '成片', '素材']), R.choice([2023, 2024, 2025, 2026]), R.randint(1, 12), R.randint(1, 28), R.randint(0, 235959)), rsize('mp4'), rand_mt()); n += 1
    for i in range(160):
        put('%s/视频/活动记录/DJI_%04d.MP4' % (HOME, R.randint(1, 9999)), rsize('MP4'), rand_mt(T(2023, 1, 1), HI)); n += 1
    for nm in ['待办事项.txt', '临时笔记.md', 'WPS 文字.desktop', 'WPS 表格.desktop', '终端.desktop', '千寻.desktop']:
        put('%s/桌面/%s' % (HOME, nm), 400, rand_mt(T(2024, 1, 1), HI)); n += 1
    return n


def gen_backups(total):
    n = 0
    snaps = ['2025-12-31', '2026-03-31', '2026-06-30', '2026-09-30']
    per = total // len(snaps)
    for s in snaps:
        y, m, d = map(int, s.split('-'))
        for i in range(per):
            r = R.random()
            if r < 0.5:
                nm, ext = doc_name()
                p = '%s/备份/%s/文档/%s/%s' % (DATA, s, R.choice(['项目方案', '会议纪要', '合同', '预算', '培训', '标准']), nm)
            elif r < 0.8:
                ext = R.choice(['c', 'h', 'py', 'cpp'])
                p = '%s/备份/%s/工作区/%s/src/%s/%s_%s.%s' % (DATA, s, R.choice(REPOS), R.choice(MODS), R.choice(SUBM), R.choice(SUBM), ext)
            else:
                ext = 'jpg'
                p = '%s/备份/%s/图片/IMG_%d%02d%02d_%06d.jpg' % (DATA, s, y - R.randint(0, 2), R.randint(1, 12), R.randint(1, 28), R.randint(0, 235959))
            put(p, rsize(ext), T(y, m, d, 2, R.randint(0, 59))); n += 1
    return n


def backdate_usr():
    out = subprocess.run(['find', '/usr', '-xdev', '-path', '/usr/local', '-prune', '-o', '-newermt', datetime.date.today().isoformat(), '-print0'],
                         capture_output=True).stdout.split(b'\0')
    mt = T(2026, 6, 10, 3, 14)
    k = 0
    for p in out:
        if p:
            try:
                os.utime(p, (mt, mt), follow_symlinks=False)
                k += 1
            except OSError:
                pass
    return k


def fix_dir_mtimes():
    allm = dict(dir_mt)
    for d in sorted(dirs_made, key=lambda x: -x.count('/')):
        m = allm.get(d)
        if m is None:
            m = rand_mt()
            allm[d] = m
        p = os.path.dirname(d)
        if p in dirs_made and allm.get(p, 0) < m:
            allm[p] = m
    for d in dirs_made:
        m = min(allm[d], NOW - 3600)
        os.utime(d, (m, m))
    for d in (HOME, DATA):
        os.utime(d, (T(2026, 10, 1), T(2026, 10, 1)))


def main():
    t0 = time.time()
    wipe()
    showcase(); print('showcase', nfiles, flush=True)
    s = SCALE
    print('photos', gen_photos(int(70000 * s)), nfiles, flush=True)
    print('home misc', gen_home_misc(), nfiles, flush=True)
    tot = 0
    for i, rp in enumerate(REPOS):
        node = rp == 'web-dashboard'
        tgt = int((24000 if node else R.randint(2500, 6500)) * s)
        root = HOME + '/工作区/' + rp if i % 2 == 0 else DATA + '/项目归档/代码库/' + rp
        tot += gen_repo(root, tgt, node)
    print('repos', tot, nfiles, flush=True)
    print('projects', gen_projects(int(150000 * s)), nfiles, flush=True)
    print('library', gen_library(int(55000 * s)), nfiles, flush=True)
    print('logs', gen_logs(int(190000 * s)), nfiles, flush=True)
    print('datasets', gen_datasets(int(150000 * s)), nfiles, flush=True)
    print('backups', gen_backups(int(160000 * s)), nfiles, flush=True)
    fix_dir_mtimes()
    print('backdated /usr files:', backdate_usr())
    print('files %d, dirs %d, time %.0fs' % (nfiles, len(dirs_made), time.time() - t0))


if __name__ == '__main__':
    main()
