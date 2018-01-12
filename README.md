# ikabot

Ikabot es un script facilita mucho el crecer rapido en ikariam.

_Es como usar una cuenta premium solo que con más funcionalidad y sin gastar una sola ambrosia._

Sus funcionalidades son:
1) Lista de construcción

	Uno puede configurar que el script suba N niveles de un edificio cualquiera.
	
2) Enviar recursos 

	Enviar cualquier cantidad de recursos de una ciudad a otra. Por ejemplo uno puede mandar medio millón de madera de la ciudad A a la ciudad B y el script se encargara de hacer los envios necesarios
	
3) Estado de la cuenta

	Muestra informacion como niveles de los edificios, tiempo hasta que se acabe el vino, recursos entre otras cosas de todas las ciudades.
	
4) Donar

	Le permite a uno donar.
	
5) Buscar espacios nuevos

	Esta funcionalidad le envia un mensaje por telegram a uno si la cantidad de espacios disponible en cualquiera de sus islas varia (aumentando o disminuyendo).
	
	Para poder configurarlo, hay que tener la aplicacion de telegram y crear un bot.
	
6) Entrar diariamente

	Para aquellos que no quieren que pase ni un dia sin que su cuenta inicie sesion.
7) Alertar ataques

	Nos alerta por telegram si nos van a atacar, de manera similar que con 5), se necesita configurar telegram.

Cuando uno setea una accion, la misma se realiza en un proceso de fondo, el cual va a correr hasta que termine o hasta que la computadora se apague.

Uno puede entrar en la cuenta sin problemas aun si hay un proceso que esta accediendola periodicamente (subiendo un edificio por ejemplo).

### Como usarlo:

simplemente ejecuten

	git clone https://github.com/santipcn/ikabot.git ~
	sudo echo 'python3 ~/ikabot/ikariam.py' > /bin/ikabot
	
y con el comando `ikabot` podran ejecutar el script.

Por el momento no funciona en windows, aunque si se tiene windows 10 se lo puede ejecutar en el bash de ubuntu.
