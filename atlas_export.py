#!/usr/bin/env Python
# -*- coding: utf-8 -*-


from math import floor
from PyQt4.QtCore import *
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
import re
project_path = ""
def run_script(iface):
    global project_path
    project_path = str(QgsProject.instance().homePath()) #Recupère le dossier du projet en cours
  
    relative_folder = "/export/" #Chemin relatif du dossier d'export par rapport au projet
    uv_field_name = "uv" #Nom du champ des valeurs uniques
    format = "png" # Autorisés unqiuement les formats raster. Pas de pdf ni de svg pour l'instant
    
    folder = project_path + relative_folder
    
    layer = iface.activeLayer()#NB : utilise la couche sélectionnée dans le contrôle des couches
    compo = iface.activeComposers()[0] #NB : changer l'index si besoin d'un autre composeur

    
    uv_field_id = layer.fieldNameIndex(uv_field_name)
    fieldsMap = layer.dataProvider().fields()
    field = fieldsMap.field(uv_field_id)
    field_type = str(field.type()).lower()
    layerSubset = layer.subsetString()
    
    expressionFind = findExpressions(compo, layer)
   
    # uniqValues = layer.dataProvider().uniqueValues(uv_field_id)
    uniqValues = layer.uniqueValues(uv_field_id)
    uv_num = len(uniqValues)
    for uv_page, uv in enumerate(uniqValues):
        if uv_num>1:
            if layerSubset!='':
                substring = '(' + layerSubset + ') AND '
            else:
                substring = ''
            substring += uv_field_name + ' = '
            if field_type in ["int", "integer", "numeric", "real", "double", "float", "bool", "boolean"]:
                substring += uv
            else:
                substring += "'" + uv.replace("'", "''") + "'"
            layer.setSubsetString(substring)
            print substring.encode('utf-8')
            print folder
            print uv.encode('utf-8')
         

        replaceExpressions(expressionFind, layer, uv, uv_page+1, uv_num)
        
        print folder
        exportCompo(compo, folder+uv+"." + format)
        
    layer.setSubsetString(layerSubset)
    resetExpressions(expressionFind)

def expressionValid(mg, layer):
    list_without_fieldname = ['VALUE', 'PAGE', 'NUM', 'NUM_ROWS', 'PROJECT_PATH']
    list_with_fieldname = ['FIELD', 'MAX', 'MIN', 'CONCAT']
    fields = layer.dataProvider().fields()
    
    if mg.group(1) in list_without_fieldname:
        return (mg.group(2)=='')
    if mg.group(1) in list_with_fieldname:
        return (fieldIndex(layer, mg.group(2)))
    return False
    
def fieldIndex(layer, fieldname):
    fieldname = str(fieldname)
    if layer.fieldNameIndex(fieldname):
        return layer.fieldNameIndex(fieldname)
    else:
        return False
    
def findExpressions(compo, layer):
    """Génère un dico résultat comprenant la liste """
    result = {'labels':[],'labelsText':[],'FIELD':[],'MAX':[],'MIN':[],'CONCAT':[]}
    
    for label in [item for item in compo.composition().items() if item.type() == QgsComposerItem.ComposerLabel]:
        mgs = [mg for mg in re.finditer('\$UV_(\w*)\((\w*)\)', label.text()) if expressionValid(mg, layer)]
        if len(mgs)>0:
            result['labels'].append(label)
            result['labelsText'].append(label.text())
            for mg in mgs:
                if mg.group(2)!='' and fieldIndex(layer,mg.group(2)) not in result[str(mg.group(1))]:
                    result[str(mg.group(1))].append(fieldIndex(layer,mg.group(2)))
    return result

def replaceExpressions(findResult, layer, uv, uv_page, uv_num):
    global project_path
    
    if len(findResult['labels'])==0:
        return True
    
    values = {
        'FIELD':{},
        'MAX':{},
        'MIN':{},
        'CONCAT':{}, 
        'VALUE':str(str.replace(uv.encode('utf-8'), '_', ' ')), 
        'PAGE':str(uv_page), 
        'NUM':str(uv_num), 
        'NUM_ROWS':str(layer.featureCount()), 
        'PROJECT_PATH':project_path
    }
    if len(findResult['FIELD'])>0:
        layerIterator = layer.getFeatures();
        feat = layerIterator.next()
        
        for fieldIdx in findResult['FIELD']:
            values['FIELD'][fieldIdx] = str(feat[fieldIdx])
        del feat
    for fieldIdx in findResult['MAX']:
        values['MAX'][fieldIdx] = str(layer.dataProvider().maximumValue(fieldIdx))
    for fieldIdx in findResult['MIN']:
        values['MIN'][fieldIdx] = str(layer.dataProvider().minimumValue(fieldIdx))
    for fieldIdx in findResult['CONCAT']:
        values['CONCAT'][fieldIdx] = ''
        for value in layer.dataProvider().uniqueValues(fieldIdx):
            if  values['CONCAT'][fieldIdx] != '':
                values['CONCAT'][fieldIdx] += ', '
            values['CONCAT'][fieldIdx] += str(value)
          
    for i, label in enumerate(findResult['labels']):
        initialValue = findResult['labelsText'][i]
        pos = 0
        outText = ''
        for mg in[mg for mg in re.finditer('\$UV_(\w*)\((\w*)\)', initialValue) if expressionValid(mg, layer)]:
            outText +=  initialValue[pos:mg.start()]
            if str(mg.group(1)) in ['VALUE','PAGE','NUM','NUM_ROWS','PROJECT_PATH']:
                value = values[str(mg.group(1))]
            else:
                value = values[str(mg.group(1))][fieldIndex(layer, mg.group(2))]
            outText += value.decode('utf-8')
            pos = mg.end()
        outText +=  initialValue[pos:]
        label.setText(outText)  
    
def resetExpressions(findResult):
    """Remettre à leur valeur initiale les zones de texte de la mise en page"""
    for i, label in enumerate(findResult['labels']):
        label.setText(findResult['labelsText'][i])

def exportCompo(composer, filePath):
    composition = composer.composition()
    saved_plot_style = composition.plotStyle()
    composition.setPlotStyle(QgsComposition.Print)
    QApplication.setOverrideCursor(Qt.BusyCursor)
    targetArea, image = renderCompositionAsRaster(composition)
    image.save(filePath)
    QApplication.restoreOverrideCursor()
    composition.setPlotStyle(saved_plot_style)
def renderCompositionAsRaster(composition):
    width = floor(composition.printResolution() * composition.paperWidth() / 25.4)
    height = floor(composition.printResolution() * composition.paperHeight() / 25.4)
    image = QImage(QSize(width, height), QImage.Format_ARGB32)
    image.setDotsPerMeterX(composition.printResolution() / 25.4 * 1000)
    image.setDotsPerMeterY(composition.printResolution() / 25.4 * 1000)
    image.fill(0)
    imagePainter = QPainter(image)
    sourceArea = QRectF(0, 0, composition.paperWidth(), composition.paperHeight())
    targetArea = QRectF(0, 0, width, height)
    composition.render(imagePainter, targetArea, sourceArea)
    imagePainter.end()
    return targetArea, image
