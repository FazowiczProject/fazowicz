@echo off
kubectl apply -f ns/
kubectl apply -f cm/
kubectl apply -f pvc/
kubectl apply -f rcs/
pause