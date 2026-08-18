@echo off
chcp 65001 >nul
REM ============================================================
REM LandVISION - PostgreSQL postgres 用户密码一键重置脚本
REM 用法：右键本文件 -> 以管理员身份运行
REM 效果：将 postgres 用户密码重置为 postgres（不丢失任何数据）
REM ============================================================
set PGDATA=C:\Program Files\PostgreSQL\16\data
set PGBIN=C:\Program Files\PostgreSQL\16\bin
set SVC=postgresql-x64-16

echo [1/6] 备份认证配置文件...
copy /Y "%PGDATA%\pg_hba.conf" "%PGDATA%\pg_hba.conf.bak" >nul

echo [2/6] 临时切换为无密码认证（trust）...
powershell -Command "(Get-Content -LiteralPath '%PGDATA%\pg_hba.conf' -Encoding Ascii) -replace 'scram-sha-256','trust' | Set-Content -LiteralPath '%PGDATA%\pg_hba.conf' -Encoding Ascii"

echo [3/6] 重启 PostgreSQL 服务...
net stop %SVC%
net start %SVC%
timeout /t 3 /nobreak >nul

echo [4/6] 重置 postgres 用户密码为 postgres...
"%PGBIN%\psql.exe" -h 127.0.0.1 -U postgres -d postgres -c "ALTER USER postgres PASSWORD 'postgres';"

echo [5/6] 恢复安全认证配置（scram-sha-256）...
copy /Y "%PGDATA%\pg_hba.conf.bak" "%PGDATA%\pg_hba.conf" >nul

echo [6/6] 再次重启服务使配置生效...
net stop %SVC%
net start %SVC%
timeout /t 3 /nobreak >nul

echo.
echo ============================================================
echo  完成！postgres 用户密码已重置为：postgres
echo  请回到对话中告诉我"已重置"，我将继续完成数据库入库。
echo ============================================================
pause
