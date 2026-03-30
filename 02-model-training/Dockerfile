FROM harbor.euso.kr/iris/demo:base
ENV PYTHONUNBUFFERED 1
ENV GIT_PYTHON_REFRESH=quiet
# RUN mkdir /workspace
WORKDIR /workspace
COPY . /workspace/
RUN pip install -r requirements.txt

