img=yt2jf_playsync
tag=0.3.1
full_img=$img:$tag
code_verison=$(git rev-parse HEAD)
echo "[core]
docker_version=$tag
code_version=$code_verison" > version.txt
docker build -t $full_img .