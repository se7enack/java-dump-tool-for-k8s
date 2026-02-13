# java-dump-tool-for-k8s
A lightweight web-based utility for generating and downloading Java thread dumps, Java heap dumps, and Java Flight Recorder (JFR) data from Java applications running inside Kubernetes pods. 
<br>

## Set cluster context:
```
kubectl config use-context <cluster>
```

<br>

## Running The App
(2 Options)

<br>

### Option 1: Using Docker (one click)
```
bash ./runtool.sh
```
* Limitation:
<i>Option 1 will not work with local k8s clusters (running on your laptop) using 127.0.0.1 as an address in the kube config. 
This confuses the container as that address routes to back itself rather than the host. Use Option 2 if this is needed.</i>


<br>

### Option 2: Native Python
```
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
python3 ./app.py
```
* open a browser to http://localhost:5001


<br>

## Screenshot:
<img width="826" height="422" alt="Screenshot" src="https://github.com/user-attachments/assets/85cf3eb4-cb44-4d09-9389-cf663c1141db" />

![](https://komarev.com/ghpvc/?username=se7enack&style=pixel)
