#!/bin/bash

# ArborGraph 项目启动脚本
# 简化版本，用于快速启动服务
# 说明：已移除旧 Gradio webui；请使用 Vue 前端（frontend/）。

# 不使用 set -e，允许某些服务启动失败时继续
set +e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_message() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  ArborGraph 项目启动${NC}"
    echo -e "${BLUE}================================${NC}"
}

# 检查 conda 环境
check_conda() {
    if ! command -v conda &> /dev/null; then
        print_error "Conda 未安装，请先安装 Anaconda 或 Miniconda"
        print_message "下载地址: https://docs.conda.io/en/latest/miniconda.html"
        exit 1
    fi
    
    if ! conda env list | grep -q "^sftgen "; then
        print_error "Conda 环境 'sftgen' 不存在"
        print_message "请先创建环境: conda env create -f environment.yml"
        exit 1
    fi
}

# 激活环境
activate_environment() {
    print_message "激活 Conda 环境..."
    eval "$(conda shell.bash hook)"
    conda activate sftgen
    # 确保 conda 环境中的 node/npm 在 PATH 中（非交互 shell 下有时缺省）
    if [ -n "${CONDA_PREFIX:-}" ]; then
        export PATH="$CONDA_PREFIX/bin:$PATH"
    fi
}

# 启动后端服务
start_backend() {
    print_message "启动 FastAPI 后端服务..."
    # 增加超时和 keepalive 配置，避免 IncompleteRead 错误
    # 统一写入 .backend.log（见 backend/logging.yaml）；进程 stdout/stderr 丢弃，避免额外 nohup.out
    nohup uvicorn backend.app:app \
        --host 0.0.0.0 \
        --port 8000 \
        --timeout-keep-alive 300 \
        --timeout-graceful-shutdown 10 \
        --log-config backend/logging.yaml \
        > /dev/null 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > .backend.pid
    sleep 1
    if kill -0 $BACKEND_PID 2>/dev/null; then
        print_message "后端服务已启动 (PID: $BACKEND_PID)"
        print_message "后端日志（含 HTTP 访问）: .backend.log"
    else
        print_error "后端服务启动失败，请查看 .backend.log（若文件未生成可检查端口/进程）"
        return 1
    fi
}

# 启动前端服务
start_frontend() {
    if [ -d "frontend" ] && command -v node &> /dev/null; then
        print_message "启动 Vue 前端服务..."
        cd frontend || {
            print_error "无法进入 frontend 目录"
            return 1
        }
        
        # 检查 node_modules 是否存在且完整，如果不存在或不完整则安装/重新安装依赖
        if [ ! -d "node_modules" ] || [ ! -f "node_modules/.bin/vite" ]; then
            if [ -d "node_modules" ]; then
                print_warning "检测到 node_modules 可能损坏，清理并重新安装..."
                rm -rf node_modules
            else
                print_message "安装前端依赖..."
            fi
            
            # 清理 npm 缓存（可选，但有助于解决依赖问题）
            print_message "清理 npm 缓存..."
            npm cache clean --force 2>/dev/null || true
            
            # 重新安装依赖
            print_message "安装前端依赖（这可能需要几分钟）..."
            npm install || {
                print_error "前端依赖安装失败"
                print_message "请尝试手动执行: cd frontend && rm -rf node_modules package-lock.json && npm install"
                cd ..
                return 1
            }
        fi
        
        # 启动开发服务器（vite.config.ts 中已配置 host: '0.0.0.0'）
        print_message "启动 Vite 开发服务器..."
        # 使用不同的方式启动，兼容 Windows/WSL
        if command -v nohup &> /dev/null; then
            # Linux/Unix 环境
            nohup npm run dev > ../.frontend.log 2>&1 &
            FRONTEND_PID=$!
        else
            # Windows/WSL 环境，使用 start 命令或直接后台运行
            npm run dev > ../.frontend.log 2>&1 &
            FRONTEND_PID=$!
        fi
        
        echo $FRONTEND_PID > ../.frontend.pid
        cd ..
        
        # 等待一下确保服务启动
        sleep 3
        
        # 检查进程是否还在运行（兼容不同系统）
        if command -v ps &> /dev/null; then
            if ps -p $FRONTEND_PID > /dev/null 2>&1 || kill -0 $FRONTEND_PID 2>/dev/null; then
                print_message "前端服务已启动 (PID: $FRONTEND_PID)"
                print_message "前端日志: .frontend.log"
                print_message "如果无法访问，请检查日志: tail -f .frontend.log"
            else
                print_error "前端服务启动失败，请查看 .frontend.log"
                print_message "尝试手动启动: cd frontend && npm run dev"
                return 1
            fi
        else
            # 如果无法检查进程，假设启动成功
            print_message "前端服务已启动 (PID: $FRONTEND_PID)"
            print_message "前端日志: .frontend.log"
            print_warning "无法验证进程状态，请手动检查服务是否运行"
        fi
    else
        if [ ! -d "frontend" ]; then
            print_warning "frontend 目录不存在，跳过前端服务启动"
        elif ! command -v node &> /dev/null; then
            print_warning "Node.js 未安装或不在 PATH 中，跳过 Vue 前端（端口 3000）"
            print_message "在已激活的 sftgen 环境中执行: conda install -c conda-forge nodejs npm"
            print_message "安装后重新运行 ./start.sh start"
        fi
    fi
}

# 停止所有服务
stop_services() {
    print_message "停止所有服务..."
    
    # 停止后端服务 (端口 8000)
    print_message "停止后端服务..."
    if [ -f .backend.pid ]; then
        BACKEND_PID=$(cat .backend.pid)
        if ps -p $BACKEND_PID > /dev/null 2>&1 || kill -0 $BACKEND_PID 2>/dev/null; then
            kill $BACKEND_PID 2>/dev/null || kill -9 $BACKEND_PID 2>/dev/null
            print_message "后端服务已停止 (PID: $BACKEND_PID)"
        fi
        rm -f .backend.pid
    fi
    
    # 通过端口查找并杀死后端进程（备用方案）
    if command -v lsof &> /dev/null; then
        BACKEND_PIDS=$(lsof -ti:8000 2>/dev/null)
        if [ -n "$BACKEND_PIDS" ]; then
            echo "$BACKEND_PIDS" | xargs kill -9 2>/dev/null
            print_message "通过端口 8000 停止后端进程"
        fi
    elif command -v netstat &> /dev/null; then
        # Windows/WSL 环境使用 netstat
        BACKEND_PIDS=$(netstat -ano | grep :8000 | grep LISTENING | awk '{print $5}' | sort -u 2>/dev/null)
        if [ -n "$BACKEND_PIDS" ]; then
            echo "$BACKEND_PIDS" | xargs kill -9 2>/dev/null || taskkill //F //PID $BACKEND_PIDS 2>/dev/null
            print_message "通过端口 8000 停止后端进程"
        fi
    fi
    
    # 通过进程名查找并杀死 uvicorn 进程（备用方案）
    if command -v pkill &> /dev/null; then
        pkill -f "uvicorn backend.app:app" 2>/dev/null && print_message "通过进程名停止后端服务"
    fi
    
    # 停止前端服务 (端口 3000)
    print_message "停止前端服务..."
    if [ -f .frontend.pid ]; then
        FRONTEND_PID=$(cat .frontend.pid)
        if ps -p $FRONTEND_PID > /dev/null 2>&1 || kill -0 $FRONTEND_PID 2>/dev/null; then
            # 前端服务可能需要杀死整个进程树
            if command -v pkill &> /dev/null; then
                pkill -P $FRONTEND_PID 2>/dev/null
            fi
            kill $FRONTEND_PID 2>/dev/null || kill -9 $FRONTEND_PID 2>/dev/null
            print_message "前端服务已停止 (PID: $FRONTEND_PID)"
        fi
        rm -f .frontend.pid
    fi
    
    # 通过端口查找并杀死前端进程（备用方案）
    if command -v lsof &> /dev/null; then
        FRONTEND_PIDS=$(lsof -ti:3000 2>/dev/null)
        if [ -n "$FRONTEND_PIDS" ]; then
            # 杀死所有相关进程（包括子进程）
            for pid in $FRONTEND_PIDS; do
                if command -v pkill &> /dev/null; then
                    pkill -P $pid 2>/dev/null
                fi
                kill -9 $pid 2>/dev/null
            done
            print_message "通过端口 3000 停止前端进程"
        fi
    elif command -v netstat &> /dev/null; then
        FRONTEND_PIDS=$(netstat -ano | grep :3000 | grep LISTENING | awk '{print $5}' | sort -u 2>/dev/null)
        if [ -n "$FRONTEND_PIDS" ]; then
            for pid in $FRONTEND_PIDS; do
                kill -9 $pid 2>/dev/null || taskkill //F //PID $pid 2>/dev/null
            done
            print_message "通过端口 3000 停止前端进程"
        fi
    fi
    
    # 通过进程名查找并杀死 vite/node 进程（备用方案）
    if command -v pkill &> /dev/null; then
        pkill -f "vite" 2>/dev/null && print_message "通过进程名停止 Vite 进程"
        # 查找 npm/node 进程
        pkill -f "npm run dev" 2>/dev/null && print_message "通过进程名停止 npm 进程"
    fi
    
    # 清理 PID 文件
    rm -f .backend.pid .frontend.pid
    
    print_message "所有服务已停止"
}

# 显示服务状态
show_status() {
    print_message "服务状态："
    echo ""
    echo "🌐 服务访问地址："
    echo "  - FastAPI 后端: http://localhost:8000"
    echo "  - Vue 前端: http://localhost:3000"
    echo ""
    echo "📋 API 文档："
    echo "  - Swagger UI: http://localhost:8000/docs"
    echo "  - ReDoc: http://localhost:8000/redoc"
    echo ""
    echo "🔧 配置："
    echo "  - 环境配置: .env"
    echo "  - 日志目录: cache/logs/"
    echo "  - 上传目录: cache/uploads/"
    echo "  - 任务目录: tasks/"
}

# 启动所有服务
start_all() {
    print_header
    check_conda
    activate_environment
    
    # 启动后端服务
    if ! start_backend; then
        print_error "后端服务启动失败"
        exit 1
    fi
    sleep 2
    
    # 启动前端服务（失败不阻止其他服务）
    if ! start_frontend; then
        print_warning "前端服务启动失败，请手动启动: cd frontend && npm run dev"
    fi
    sleep 3
    
    show_status
    print_message "所有服务已启动！"
}

# 显示帮助信息
show_help() {
    echo "ArborGraph 项目启动脚本"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  start      启动所有服务"
    echo "  stop       停止所有服务"
    echo "  restart    重启所有服务"
    echo "  status     显示服务状态"
    echo "  help       显示帮助"
    echo ""
    echo "示例:"
    echo "  $0 start    # 启动所有服务"
    echo "  $0 stop     # 停止所有服务"
}

# 主函数
main() {
    case "${1:-start}" in
        start)
            start_all
            ;;
        stop)
            stop_services
            ;;
        restart)
            stop_services
            sleep 2
            start_all
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
