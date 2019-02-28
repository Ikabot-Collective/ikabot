#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def getRecursosDisponibles(html, num=False):
	recursos = re.search(r'\\"resource\\":(\d+),\\"2\\":(\d+),\\"1\\":(\d+),\\"4\\":(\d+),\\"3\\":(\d+)}', html)
	if num:
		return [int(recursos.group(1)), int(recursos.group(3)), int(recursos.group(2)), int(recursos.group(5)), int(recursos.group(4))]
	else:
		return [recursos.group(1), recursos.group(3), recursos.group(2), recursos.group(5), recursos.group(4)]

def getCapacidadDeAlmacenamiento(html, num=False):
	almacenamiento = re.search(r'maxResources:\s*JSON\.parse\(\'{\\"resource\\":(\d+),', html).group(1)
	if num:
		almacenamiento = int(almacenamiento)
	return almacenamiento 

def getConsumoDeVino(html):
	return int(re.search(r'GlobalMenu_WineConsumption"\s*class="rightText">\s*(\d*)\s', html).group(1))
