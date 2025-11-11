#!/bin/bash
set -euo pipefail  # 严格模式：报错立即退出，禁止未定义变量，管道失败则脚本失败

##############################################################################
# 配置参数（根据你的实际环境修改！）
##############################################################################
# 1. Neo4j 连接信息（docker-compose 中配置的用户名/密码）
NEO4J_USER="neo4j"       # 默认用户名，若修改过请替换
NEO4J_PASSWORD="learning123"   # 你的 Neo4j 实际密码（首次登录后需修改）
# 2. 数据卷配置（根据 docker volume ls 查看到的实际卷名修改）
DATA_VOLUME_NAME="neo4j_neo4j_data"  # 核心数据卷（关键！替换为你的卷名）
# 3. docker-compose 相关（默认当前目录，若文件在其他路径请修改）
COMPOSE_FILE_PATH="./docker-compose.yml"  # docker-compose.yml 文件路径

##############################################################################
# 安全校验
##############################################################################
# 校验 docker-compose 文件是否存在
if [ ! -f "$COMPOSE_FILE_PATH" ]; then
    echo -e "\033[31m错误：未找到 docker-compose 文件！\n路径：$COMPOSE_FILE_PATH\033[0m"
    exit 1
fi

# 校验数据卷是否存在
if ! docker volume ls | grep -q "$DATA_VOLUME_NAME"; then
    echo -e "\033[31m错误：数据卷 $DATA_VOLUME_NAME 不存在！\n请执行 docker volume ls 查看实际卷名并修改脚本配置\033[0m"
    exit 1
fi

# 二次确认（防止误操作）
echo -e "\033[33m警告：此脚本将彻底删除 Neo4j 所有数据（含节点、关系、Property keys），且无法恢复！\033[0m"
read -p "是否继续？(y/N)：" CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo -e "\033[32m操作已取消\033[0m"
    exit 0
fi

##############################################################################
# 核心执行步骤
##############################################################################
echo -e "\n=== 步骤1：进入容器执行 Cypher 清空节点/关系/属性 ==="
# 兼容新旧版本：通过 echo 传递命令到 cypher-shell（无需 -c 参数）
echo "MATCH (n) SET n = {} DETACH DELETE n;" | \
docker-compose -f "$COMPOSE_FILE_PATH" exec -T neo4j cypher-shell \
    -u "$NEO4J_USER" \
    -p "$NEO4J_PASSWORD"

if [ $? -eq 0 ]; then
    echo -e "\033[32m✅ 节点/关系/属性清空成功\033[0m"
else
    echo -e "\033[31m❌ 节点/关系/属性清空失败！可能原因：\033[0m"
    echo "1. 用户名/密码错误（检查 NEO4J_USER 和 NEO4J_PASSWORD 配置）"
    echo "2. Neo4j 容器未正常运行（执行 docker-compose ps 查看状态）"
    exit 1
fi

echo -e "\n=== 步骤2：停止容器并删除数据卷 ==="
# 停止并移除容器（保留配置文件）
docker-compose -f "$COMPOSE_FILE_PATH" down
echo -e "✅ 容器已停止并移除"

# 删除核心数据卷（彻底清除元数据）
docker volume rm "$DATA_VOLUME_NAME"
if [ $? -eq 0 ]; then
    echo -e "✅ 数据卷 $DATA_VOLUME_NAME 已删除"
else
    echo -e "\033[31m❌ 数据卷删除失败！\033[0m"
    echo "可能原因：有其他容器占用该数据卷，执行以下命令排查："
    echo "docker volume inspect $DATA_VOLUME_NAME | grep Mountpoint"
    exit 1
fi

echo -e "\n=== 步骤3：重启容器生成全新空库 ==="
docker-compose -f "$COMPOSE_FILE_PATH" up -d
if [ $? -eq 0 ]; then
    echo -e "✅ 容器已重启，全新空库创建成功！"
else
    echo -e "\033[31m❌ 容器重启失败，请检查 docker-compose 配置（如端口占用、权限等）\033[0m"
    exit 1
fi

##############################################################################
# 最终验证提示
##############################################################################
echo -e "\n\033[32m=== 操作完成！=== \033[0m"
echo -e "验证空库命令（复制执行）："
echo -e "echo 'MATCH (n) RETURN n;' | docker-compose -f $COMPOSE_FILE_PATH exec -T neo4j cypher-shell -u $NEO4J_USER -p $NEO4J_PASSWORD"