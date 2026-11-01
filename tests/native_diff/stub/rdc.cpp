#include <windows.h>
#include <stdio.h>
int main(int c,char**v){ HANDLE h=CreateFileW(L"C:\\rdcroot",FILE_LIST_DIRECTORY,7,0,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS,0);
 char buf[65536]; DWORD t0=GetTickCount();
 while(GetTickCount()-t0<8000){ DWORD n=0; OVERLAPPED o={0}; o.hEvent=CreateEventW(0,1,0,0);
  ReadDirectoryChangesW(h,buf,sizeof buf,TRUE,0x1|0x2|0x8|0x10,0,&o,0);
  if(WaitForSingleObject(o.hEvent,500)!=0){CancelIo(h);continue;}
  GetOverlappedResult(h,&o,&n,0); FILE_NOTIFY_INFORMATION*f=(FILE_NOTIFY_INFORMATION*)buf;
  for(;;){ printf("act=%lu %.*ls\n",f->Action,(int)(f->FileNameLength/2),f->FileName); if(!f->NextEntryOffset)break; f=(FILE_NOTIFY_INFORMATION*)((char*)f+f->NextEntryOffset);} fflush(stdout);} return 0;}
