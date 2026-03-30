FROM harbor.euso.kr/iris/demo:base

RUN ln -sf /usr/share/zoneinfo/Asia/Seoul /etc/localtime && echo "Asia/Seoul" > /etc/timezone

WORKDIR /workspace
COPY . /workspace/

# ENV PATH=/usr/bin/python3:/bin:/usr/local/bin:/usr/bin