#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re

def asignarRecursoBuscado():
	data = {
	'cityId': 9999,
	'position': 9999,
	'view': 'branchOffice',
	'activeTab': 'bargain',
	'type': 999,
	'searchResource': 999,
	'range': 999,
	'backgroundView' : 'city',
	'currentCityId': 9999,
	'templateView': 'branchOffice'
	'actionRequest': 999,
	'ajax': 1
	}
	rta = s.post(payloadPost=data)

def obtenerOfertas(s):
	url = 'view=branchOffice&cityId={}&position={}&currentCityId={}&backgroundView=city&actionRequest={}&ajax=1'
	data = s.post(url)
	json_data = json.loads(data, strict=False)
	html = json_data[1][1][1]
	hits = re.findall(r'short_text80\\">(.*?) *<br\/>(.*?)\\n *<\/td>\\n *<td>(\d+)<\/td>\\n *<td>(.*?)\/td>\\n *<td><img src=\\"skin\/resources\/icon_(\w+).png.*?href=\\"\?view=takeOffer&destinationCityId=(\d+)&oldView=branchOffice&activeTab=bargain&cityId=(\d+)&position=(\d+)&type=(\d+)&resource=(\d+)\\"', html)


def comprarRecursos(s):
	data = {
	'action': 'transportOperations',
	'function': 'buyGoodsAtAnotherBranchOffice',
	'cityId': 99999,
	'destinationCityId': 999,
	'oldView': 'branchOffice',
	'position': 13,
	'avatar2Name': jugadorAComprar,
	'city2Name': ciudadDestino,
	'type': 444,
	'activeTab': 'bargain',
	'transportDisplayPrice': 0,
	'premiumTransporter': 0,
	'tradegood3Price': 10,
	'cargo_tradegood3': cargaTotal,
	'capacity': 5,
	'max_capacity': 5,
	'jetPropulsion': 0,
	'transporters': barcos,
	'backgroundView': 'city',
	'currentCityId': 99999,
	'templateView': 'takeOffer',
	'currentTab': 'bargain',
	'actionRequest': 'c271e036907bd35ce35bc4e0e2a7ce1e',
	'ajax': 1
	}

