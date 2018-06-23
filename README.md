## ikabot ~ Ikariam Bot

_Es un script escrito en python que otorga la misma y mucha más funcinoalidad que una cuenta premium en ikariam, ¡sin gastar ambrosia!_

### Funcionalidades:

1) Lista de construcción

	El usuario selecciona un edificio, la cantidad de niveles a subir, _ikabot_ calcula si se cuenta con los recursos suficientes y se encarga de subir la cantidad de niveles seleccionada.
	
2) Enviar recursos 

	Sirve para enviar cualquier cantidad de recursos de una ciudad a otra. No importa la cantidad de barcos que tenga, _ikabot_ realizara la cantidad de viajes que sean necesarios. La ciudad de destino puede ser propia o de otros jugadores.

3) Enviar vino

	Sirve para enviar vino desde las ciudades en vino, a las ciudades que no están en vino. La cantidad máxima a enviar es igual a la cantidad total de vino que hay almacenado en ciudades en vino, dividido por la cantidad de ciudades que no están en vino.

4) Estado de la cuenta

	Muestra informacion como niveles de los edificios, tiempo hasta que se acabe el vino, recursos entre otras cosas de todas las ciudades.
	
5) Donar

	Le permite a uno donar.
	
6) Buscar espacios nuevos

	Esta funcionalidad avisa por telegram, si una ciudad desapareció o si alguien fundó en cualquiera de las islas en donde el usuario tiene al menos una ciudad fundada.
	
7) Entrar diariamente

	Para aquellos que no quieren que pase ni un dia sin que su cuenta inicie sesion.
	
8) Alertar ataques

	Nos alerta por telegram si nos van a atacar.

9) Bot donador

	Entra una vez al día y dona toda la madera disponible de todas las ciudades al bien de lujo o a los aserraderos.

10) Actualizar IkaBot

	Actualiza el programa haciendo un pull a este repositorio.
	

Cuando uno configura una acción, puede entrar y jugar ikariam sin problemas. El único inconveniente que puede llegar a tener, es que la sesión expire, esto es normal y si sucede simplemente vuelva a entrar.

### Instalar:

ejecutar:

	sudo git clone https://github.com/santipcn/ikabot.git /opt/ikabot
	sudo sh -c "echo 'python3 /opt/ikabot' > /bin/ikabot" && sudo chmod +x /bin/ikabot
	
con el comando `ikabot` podran acceder al menu de acciones.

### Desinstalar:

simplemente ejecuten

	sudo rm -rf /opt/ikabot
	sudo rm /bin/ikabot

### Dependencias:

Para que _ikabot_ funcione debe estar instalado python3 y el modulo externo requests

#### - Python 3
Probablemente se encuentre instalado por defecto en su sistema.

https://www.python.org/download/releases/3.0/

#### - Pip
Es una tool para instalar paquetes de python.
Para instalarlo bajen _get-pip.py_ desde https://pip.pypa.io/en/stable/installing/ 
y corran `python3 get-pip.py`

#### - Requests
Se encarga de realizar los post, gets y el manejo de las cookies.
Para instalarlo `pip3 install requests`

http://docs.python-requests.org/en/master/

### Telegram

Algunas funcionalidades (como alertar ataques) se comunican con usted mediante mensajes de Telegram.

Los mensajes que le envia son visibles por usted y nadie más.

Configurarlo es altamente recomendable, ya que le permite a uno disfrutar de toda la funcionalidad de _ikabot_.

Para configurarlo necesitaremos simplemente ingresar dos datos:

1) El token del bot a utilizar

	Si quiere utilizar el bot 'oficial' de _ikabot_, entre en Telegram y busque con la lupa a @DaHackerBot, háblele y verá que se manda un /start. Una vez hecho esto puede cerrar Telegram.
	
	Luego, cuando _ikabot_ le pida que ingrese el token del bot, use el siguiente: `409993506:AAFwjxfazzx6ZqYusbmDJiARBTl_Zyb_Ue4`.
	
	Si quiere usar su propio bot, lo puede crear con las siguientes instrucciones: https://core.telegram.org/bots.

2) Su chat_id

	Este identificador es único de cada usuario de Telegram y lo puede conocer hablandole por telegram a @get_id_bot (el que tiene un arco de foto).

Cuando quiera usar una funcionalidad que requiera de Telegram, como al ingresar al item _(8) Alertar ataques_ en el menu, _ikabot_ se le pedirá el token del bot y su chat_id. Una vez ingresados, se guardaran en un archivo y no se volverán a pedir.


### Avanzado:

Si existe un proceso de ikabot que identificamos con `ps aux | grep ikabot`, podemos consesguir una descripción de lo que hace con `kill -SIGUSR1 <pid>`. La descripción le llegará mediante telegram.

### Windows:

Por el momento no funciona en windows, aunque si se tiene windows 10, se lo puede ejecutar en el bash de ubuntu.

