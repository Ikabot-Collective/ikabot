## ikabot ~ Ikariam Bot

_Es un script escrito en python que otorga la misma y mucha más funcinoalidad que pagar una cuenta premium en ikariam, sin gastar ambrosia._

### Funcionalidades:

1) Lista de construcción

	Uno puede configurar que el script suba N niveles de un edificio cualquiera.
	
2) Enviar recursos 

	Enviar cualquier cantidad de recursos de una ciudad a otra. Por ejemplo uno puede mandar medio millón de madera de la ciudad A a la ciudad B y el script se encargara de hacer los envios necesarios

3) Enviar vino

	Envia una cantidad igual de vino a todas las ciudades. Esto se hace solo una vez, por ende se recomienda mandar tanto como se pueda. La maxima cantidad a enviar se calcula automaticamente.

4) Estado de la cuenta

	Muestra informacion como niveles de los edificios, tiempo hasta que se acabe el vino, recursos entre otras cosas de todas las ciudades.
	
5) Donar

	Le permite a uno donar.
	
6) Buscar espacios nuevos

	Esta funcionalidad le envia un mensaje por telegram a uno si la cantidad de espacios disponible en cualquiera de sus islas varia (aumentando o disminuyendo).
	
	Para poder configurarlo, hay que tener la aplicacion de telegram y crear un bot.
	
7) Entrar diariamente

	Para aquellos que no quieren que pase ni un dia sin que su cuenta inicie sesion.
8) Alertar ataques

	Nos alerta por telegram si nos van a atacar, de manera similar que con 5., se necesita configurar telegram.

9) Bot donador

	Entra una vez al día y dona toda la madera disponible de todas las ciudades al bien de lujo o a los aserraderos.

10) Actualizar IkaBot

	Actualiza el programa haciendo un pull a este repositorio.

Cuando uno setea una accion, la misma se realiza en un proceso de fondo, el cual va a correr hasta que termine o hasta que la computadora se apague o se mate el proceso.

Uno puede entrar en la cuenta sin problemas aun si hay un proceso que esta accediendola periodicamente (subiendo un edificio, por ejemplo).

### Instalación:

simplemente ejecuten

	git clone https://github.com/santipcn/ikabot.git ~
	sudo sh -c "echo \"python3 ~/ikabot" > /bin/ikabot" && sudo chmod +x /bin/ikabot
	
y con el comando `ikabot` podran ejecutar el script.

### Dependencias:

Para que ikabot funcione debe estar instalado python3 y el modulo externo requests
#### Python 3
Probablemente se encuentre instalado por defecto en su sistema.
https://www.python.org/download/releases/3.0/
#### Requests
Se encarga de realizar los post, gets y el manejo de las cookies.
http://docs.python-requests.org/en/master/

### Avanzado:

Si existe un proceso de ikabot que identificamos con `ps aux | grep ikabot` podemos consesguir una descripción de lo que hace con `kill -SIGUSR1 <pid>`.

### Windows

Por el momento no funciona en windows, aunque si se tiene windows 10 se lo puede ejecutar en el bash de ubuntu.

