千寻（QianXun）使用说明

一、简介

千寻是一款 Everything 式的文件名秒搜工具，面向银河麒麟（Galaxy Kylin）Linux。建立索引后，可按文件名瞬间检索全盘文件。本包离线自带运行库，支持 x86_64 与飞腾 arm64 架构。

二、使用方法

首次使用前建议先运行自检：在解压目录打开终端，执行 sh check.sh，按提示确认能否运行；报告保存在 check-report.txt。

按 CPU 架构选包（终端执行 uname -m 查看）：x86_64 选 amd64／x86_64 包；aarch64（飞腾）选 arm64／aarch64 包。两类包均自带 Python 与 Qt 运行库，无需联网安装任何依赖。

1. 绿色版：解压后双击 qianxun.sh，或在终端中进入目录运行 ./qianxun.sh。
2. 用户安装：运行 ./install.sh，可加 --autostart 同时设置登录后自动启动（后台隐藏运行）。程序安装到 ~/.local/share/qianxun，并在应用菜单与桌面创建快捷方式，终端可直接输入 qianxun 启动。
3. 系统级安装：sudo ./install.sh --system（安装到 /opt/qianxun，所有用户可用）。
4. deb 包：sudo dpkg -i qianxun_*.deb
5. 卸载：./uninstall.sh（加 --purge 同时删除配置与缓存；系统级卸载使用 sudo ./uninstall.sh --system）。

解压注意事项（绿色版）：
（1）请先把压缩包复制到本机硬盘（如“主目录”或“桌面”）再解压，不要直接在 U 盘里解压。U 盘多为 FAT32／exFAT／NTFS 格式，不支持 Linux 的可执行权限，解压会报错或解压后无法运行。若确实从 U 盘运行，程序首次启动会自动复制到 ~/.local/share/qianxun-portable 再运行。
（2）终端解压命令：tar -xzf qianxun-1.1.0-kylin-aarch64.tar.gz（x86 机器把 aarch64 换成 x86_64）。若下载后文件名变成 .tar（浏览器已自动解开一层），改用 tar -xf 文件名。
（3）也可使用同版本的 .zip 包，双击用“归档管理器”解压，或执行 unzip 文件名。
（4）解压报错时，先核对文件是否完整：sha256sum 文件名，与 SHA256SUMS.txt 中的值比对，不一致说明拷贝或下载不完整，需重新拷贝。

三、搜索语法

语法｜含义｜示例
------------------------------------------------------------
空格｜与（同时满足多个词）｜report 2026
|｜或｜jpg|png
!｜非（排除）｜report !draft
* 与 ?｜通配符（* 任意多个字符，? 单个字符）｜*.log、file?.txt
“...”｜精确短语（含空格的词）｜“project plan”
ext:｜按扩展名（多个用分号分隔）｜ext:pdf;docx
file:｜仅匹配文件｜file: 报告
folder:｜仅匹配文件夹｜folder: 归档
path:｜按路径匹配（含 / 的词自动按路径匹配）｜path:/home/user/docs
regex:｜正则表达式｜regex:^IMG_\d+
size:｜按大小：>10mb、1mb..10mb、large｜size:>10mb
dm:｜按修改日期：today、yesterday、thisweek、last7days、2026-10｜dm:last7days
Ctrl+I｜区分大小写（开关）｜
Ctrl+B｜全字匹配（开关）｜
Ctrl+U｜匹配路径（开关）｜
Ctrl+R｜正则模式（开关）｜

四、快捷键

Enter：打开文件
Ctrl+Enter：打开所在文件夹
Ctrl+C：复制文件
Ctrl+Shift+C：复制路径
F2：重命名
Delete：移到回收站
Esc：清空搜索框／隐藏窗口

五、全局快捷键设置

在麒麟系统“设置→设备→快捷键→自定义快捷键”中新建快捷键，命令填写：

~/.local/share/qianxun/qianxun.sh --toggle

或（已完成用户安装时）：

qianxun --toggle

例如绑定 Alt+空格。再次按下可显示或隐藏主窗口。

六、常见问题

（1）麒麟安全中心提示“未知来源／未签名应用被阻止”时，请在“安全中心→应用控制与保护”中允许或添加信任。
（2）普通用户无权读取的目录（如 /root）不会被索引。
（3）实时监控目录数受系统 inotify 上限约束，超出部分每 3 分钟轮询更新。可在“工具→提升实时监控上限”中一键提升（需管理员密码）。
（4）索引缓存位于 ~/.cache/qianxun，配置位于 ~/.config/qianxun。
（5）运行库选择：若系统已装有 python3-pyqt5，程序优先使用系统库（输入法、主题与系统一致）；否则使用包内自带运行库。两类包内运行库均已带 fcitx（兼容 fcitx4／fcitx5）与 ibus 输入法插件。可用环境变量 QIANXUN_MODE=system／syspyqt／bundled 强制指定。
（6）飞腾 arm64 包内运行库为 Qt6。若个别机型搜索框无法输入中文，可先粘贴关键词搜索；系统装有 python3-pyqt5 时程序会自动改用系统库。
（7）搜索结果超过 30 万条时，切换排序需 1～2 秒，属正常现象；输入关键词缩小范围后即为瞬时。
