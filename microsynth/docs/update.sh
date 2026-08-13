date +"Start: %Y-%m-%d %H:%M-%S"

echo "pull code: erpnext"
cd /home/frappe/frappe-bench/apps/erpnext
git pull

echo "pull code: erpnextaustria"
cd /home/frappe/frappe-bench/apps/erpnextaustria
git pull

echo "pull code: erpnextswiss"
cd /home/frappe/frappe-bench/apps/erpnextswiss
git pull

echo "pull code: frappe"
cd /home/frappe/frappe-bench/apps/frappe
git pull

echo "pull code: microsynth"
cd /home/frappe/frappe-bench/apps/microsynth
git pull

echo "pull code: frappe"
cd /home/frappe/frappe-bench/apps/frappe
git pull

echo "set permissions"
cd /home/frappe/frappe-bench/apps
chown -R frappe:frappe *

echo "migrate erp-test.microsynth.local"
bench --site erp-test.microsynth.local migrate

echo "migrate erp.microsynth.local"
bench migrate

echo "restart bench"
bench restart

echo "restart supervisor"
service supervisor restart

date +"Finish: %Y-%m-%d %H:%M-%S"
