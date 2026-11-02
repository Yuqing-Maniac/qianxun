import sys, os
os.environ['QIANXUN_LAUNCHER'] = r'C:\qxport\QianXun\QianXun.exe'
sys.path.insert(0, r'C:\qxport\QianXun\app')
import qianxun as q
out = open(r'C:\qxport\integ.txt', 'w', encoding='utf-8')
q.win_autostart_set(True); out.write('autostart=%r\n' % q.win_autostart_get())
q.win_autostart_set(False); out.write('after off=%r\n' % q.win_autostart_get())
app = q.QApplication([])
desk = q._QtCore.QStandardPaths.writableLocation(q._QtCore.QStandardPaths.DesktopLocation)
lnk = os.path.join(desk, '千寻.lnk')
ok = q._QtCore.QFile.link(r'C:\qxport\QianXun\QianXun.exe', lnk)
out.write('desktop=%s link ok=%s exists=%s target=%s\n' % (desk, ok, os.path.exists(lnk), q._QtCore.QFileInfo(lnk).symLinkTarget()))
if os.path.exists(lnk): os.remove(lnk)
out.write('props=%r\n' % q.win_show_properties(r'C:\demo'))
open(r'C:\demo\rb.txt','w').write('x')
out.write('recycle(SHFileOperationW)=%r gone=%r\n' % (q.win_recycle(r'C:\demo\rb.txt'), not os.path.exists(r'C:\demo\rb.txt')))
out.write('drive type C=%d Z=%d\n' % (q.win_drive_type('C:\\x'), q.win_drive_type('Z:\\x')))
out.close()
