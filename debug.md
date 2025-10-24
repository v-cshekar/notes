
Can you try this upgrade path manually and seen if we have a repro too?

This is double upgrade path test (A -> B -> B).  So upgrade path is ->cold->202411-warm->202505-warm->202505
If we see this here, then also try  B->B->B: ->cold->202505-warm->202505-warm->202505

Shell
2025 Aug 26 16:25:29.739166 gd383 WARNING syncd#syncd: :- logViewObjectCount: object count for SAI_OBJECT_TYPE_BUFFER_POOL on current view 5 is different than on temporary view: 3
2025 Aug 26 16:25:30.468381 gd383 NOTICE syncd#syncd: :- executeOperationsOnAsic: operations on SAI_OBJECT_TYPE_BUFFER_POOL: 2
2025 Aug 26 16:25:30.468381 gd383 NOTICE syncd#syncd: :- executeOperationsOnAsic: operations on SAI_OBJECT_TYPE_BUFFER_PROFILE: 5
2025 Aug 26 16:25:30.471587 gd383 ERR syncd#syncd: [none] SAI_API_BUFFER:brcm_sai_remove_buffer_pool:2314 Buffer pool 0x0000001800000002 is in use with ref count 2
2025 Aug 26 16:25:30.471587 gd383 ERR syncd#syncd: :- asic_handle_generic: remove SAI_OBJECT_TYPE_BUFFER_POOL RID: oid:0x1800000002 VID oid:0x180000000019cb failed: SAI_STATUS_OBJECT_IN_USE
2025 Aug 26 16:25:30.471587 gd383 ERR syncd#syncd: :- asic_process_event: failed to execute api: remove, key: SAI_OBJECT_TYPE_BUFFER_POOL:oid:0x180000000019cb, status: SAI_STATUS_OBJECT_IN_USE
2025 Aug 26 16:25:30.472134 gd383 NOTICE syncd#syncd: :- executeOperationsOnAsic: asic apply took 0.009552 sec
2025 Aug 26 16:25:30.472134 gd383 ERR syncd#syncd: :- executeOperationsOnAsic: Error while executing asic operations, ASIC is in inconsistent state: :- asic_process_event: failed to execute api: remove, key: SAI_OBJECT_TYPE_BUFFER_POOL:oid:0x180000000019cb, status: SAI_STATUS_OBJECT_IN_USE
2025 Aug 26 16:25:30.532928 gd383 NOTICE syncd#syncd: :- threadFunction



# Upgrade Warm reboot test from A->B

1. Make sure device is stable
admin@strtk5-7260-01:~$ show ip bgp sum
admin@strtk5-7260-01:~$ show ip int
admin@strtk5-7260-01:~$ show int portchannel
docker ps -a

2. Install verstion A image and perform cold reboot

sudo sonic_installer install -y http://10.201.148.43/pipelines/Networking-acs-buildimage-Official/broadcom/internal-202411/tagged/sonic-aboot-broadcom.swi

admin@strtk5-7260-01:~$ sudo reboot

3. After system comes up, check and upgrade image B, perform warm reboot

admin@strtk5-7260-01:~$ sudo sonic_installer list
admin@strtk5-7260-01:~$ show ip bgp sum
admin@strtk5-7260-01:~$ show ip int
admin@strtk5-7260-01:~$ show int portchannel
df -h
sudo zramctl
free -h

# Upgrade Warm reboot test from B->B
sudo sonic_installer install -y http://10.201.148.43/pipelines/Networking-acs-buildimage-Official/broadcom/internal-202505/tagged/sonic-aboot-broadcom.swi
admin@strtk5-7260-01:~$ sudo warm-reboot -vvv

4. When system comes up, check status
admin@strtk5-7260-01:~$ show version
admin@strtk5-7260-01:~$ show ip bgp sum
admin@strtk5-7260-01:~$ show ip int
admin@strtk5-7260-01:~$ show int portchannel

Check the logs


sudo sonic_installer install -y http://10.201.148.43/pipelines/Networking-acs-buildimage-Official/broadcom/internal-202505/tagged/sonic-aboot-broadcom.swi
admin@strtk5-7260-01:~$ sudo warm-reboot -vvv

check the logs