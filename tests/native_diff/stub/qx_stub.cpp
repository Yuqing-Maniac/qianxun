// Minimal stand-in for QianXun --cli (harness validation only): plain case-insensitive substring match on names.
// Also: --dump-args (echo argv as UTF-8 lines) and --dump-attrs <dir> (print attributes of entries).
#include <windows.h>
#include <string>
#include <vector>
#include <algorithm>
#include <cstdio>
#include <cwchar>
using namespace std;
static string u8(const wstring& w){ if(w.empty()) return ""; int n=WideCharToMultiByte(CP_UTF8,0,w.data(),(int)w.size(),0,0,0,0); string s(n,0); WideCharToMultiByte(CP_UTF8,0,w.data(),(int)w.size(),&s[0],n,0,0); return s; }
static wstring low(wstring s){ if(!s.empty()) CharLowerBuffW(&s[0],(DWORD)s.size()); return s; }
struct E{ wstring path,name; bool dir; };
static void scan(const wstring& d, vector<E>& out){
  WIN32_FIND_DATAW fd; wstring pat = (d.compare(0,4,L"\\\\?\\")==0? d : L"\\\\?\\"+d) + L"\\*";
  HANDLE h = FindFirstFileExW(pat.c_str(), FindExInfoBasic, &fd, FindExSearchNameMatch, 0, FIND_FIRST_EX_LARGE_FETCH);
  if(h==INVALID_HANDLE_VALUE) return;
  do{
    if(!wcscmp(fd.cFileName,L".")||!wcscmp(fd.cFileName,L"..")) continue;
    bool dir = fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY;
    E e; e.name=fd.cFileName; e.path=d+L"\\"+e.name; e.dir=dir; out.push_back(e);
    if(dir && !(fd.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) scan(e.path,out);
  }while(FindNextFileW(h,&fd));
  FindClose(h);
}
int wmain(int argc, wchar_t** argv){
  wstring root, query, outf; bool cli=false, watch=false, dumpargs=false; wstring dumpattrs; int dur=5;
  for(int i=1;i<argc;i++){ wstring a=argv[i];
    if(a==L"--cli") cli=true; else if(a==L"--cli-watch"){cli=true;watch=true;}
    else if(a==L"--dump-args") dumpargs=true;
    else if(a==L"--dump-attrs"&&i+1<argc) dumpattrs=argv[++i];
    else if(a==L"--root"&&i+1<argc) root=argv[++i];
    else if(a==L"--query"&&i+1<argc) query=argv[++i];
    else if(a==L"--out"&&i+1<argc) outf=argv[++i];
    else if(a==L"--duration"&&i+1<argc) dur=_wtoi(argv[++i]);
  }
  if(dumpargs){ for(int i=1;i<argc;i++) printf("[%s]\n",u8(argv[i]).c_str()); return 0; }
  if(!dumpattrs.empty()){
    WIN32_FIND_DATAW fd; HANDLE h=FindFirstFileExW((dumpattrs+L"\\*").c_str(),FindExInfoBasic,&fd,FindExSearchNameMatch,0,0);
    if(h==INVALID_HANDLE_VALUE) return 1;
    do{ printf("%08lx tag=%08lx %s\n",fd.dwFileAttributes,fd.dwReserved0,u8(fd.cFileName).c_str()); }while(FindNextFileW(h,&fd));
    return 0; }
  if(!cli) return 2;
  while(!root.empty() && root.back()==L'\\' && root.size()>3) root.pop_back();
  vector<E> v; scan(root,v);
  wstring q=low(query);
  auto run=[&](vector<wstring>& res){ res.clear(); for(auto&e:v) if(q.empty()||low(e.name).find(q)!=wstring::npos) res.push_back(e.path);
    sort(res.begin(),res.end(),[&](const wstring&a,const wstring&b){ wstring la=low(a.substr(a.rfind(L'\\')+1)),lb=low(b.substr(b.rfind(L'\\')+1)); return la!=lb? la<lb : a<b; }); };
  FILE* f=_wfopen(outf.c_str(),L"wb"); if(!f) return 3;
  if(!watch){ DWORD t0=GetTickCount(); vector<wstring> r; run(r); DWORD ms=GetTickCount()-t0;
    for(auto&s:r) fprintf(f,"%s\n",u8(s).c_str()); fprintf(f,"#count=%zu #ms=%lu\n",r.size(),(unsigned long)ms); }
  else { DWORD t0=GetTickCount(); while(GetTickCount()-t0 < (DWORD)dur*1000){ vector<E> v2; scan(root,v2); v.swap(v2); vector<wstring> r; run(r);
      fprintf(f,"%lu %zu\n",(unsigned long)(GetTickCount()-t0),r.size()); fflush(f); Sleep(100);} }
  fclose(f); return 0; }
