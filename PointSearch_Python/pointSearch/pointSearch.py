from __main__ import vtk, qt, ctk, slicer
from copy import deepcopy
import os, re
import sitkUtils, sys
from slicer.ScriptedLoadableModule import *
import Tkinter as tk, tkFileDialog
import time
import io

class pointSearch(ScriptedLoadableModule ):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        # Interface Captions
        parent.title        = "pointSearch"
        parent.categories   = ["VisSim"]
        parent.dependencies = []
        parent.contributors = [ ""  ]
        parent.helpText     =   ""
        parent.acknowledgementText = " "
        self.parent = parent
 


''' ========================= TODO ===============
- Fix the visual glitch when adding a point during locked mode (Point only shows after moving the view a bit)
		--Caused by locking the Fiducials before adding one
- Find a way to track additions/modifications to the table with an observer
- Set the 'Visible' cell via code
- Find a way to decrement the global Fiducial point id after removing one
- Change the opacity of unselected models
- Let the 'Export Points' button export the current Fiducial points in a Slicer-readable? fcsv file
- Let the user set a name when adding a Point? (Open a window after placing)


- Implement a Find Points method
=================================================='''

''' ========================= Working ===============
- Adding/Removing Points by Hand
- Importing Points
- Adding/Updating Point data in Table
- Importing a model
- 3D-View as default view when loading the module
- Locking/Unlocking nodes
- Editing/Renaming points by clicking them
=================================================='''
#                           Main Widget
#===================================================================
class pointSearchWidget(ScriptedLoadableModuleWidget):
    #----------------------------------------   Initialization 
    def setup(self):           
        ScriptedLoadableModuleWidget.setup(self)
        # Initialize GUI
        self.initMainPanel()
    
    

    def initMainPanel(self):

        #Set the default layout to 3D-Only
        threeDOnly = ("<layout type=\"horizontal\">"
        " <item>"
        "  <view class=\"vtkMRMLViewNode\" singletontag=\"1\">"
        "   <property name=\"viewlabel\" action=\"default\">1</property>"
        "  </view>"
        " </item>"
        "</layout>")
        threeDOnlyId=501
        layoutManager = slicer.app.layoutManager()
        layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(threeDOnlyId,threeDOnly)
        layoutManager.setLayout(threeDOnlyId)

        #Close the previous scene 
        #  !!Clears all data!!
        slicer.mrmlScene.Clear(0)

        #Layout for Add/Remove/Edit button (Probably simpler way to do this)
        def createHLayout(elements):
            widget = qt.QWidget()
            rowLayout = qt.QHBoxLayout()
            widget.setLayout(rowLayout)
            for element in elements:
              rowLayout.addWidget(element)
            return widget
        # Create main collapsible Button 
        self.mainCollapsibleButton = ctk.ctkCollapsibleButton()
        self.mainCollapsibleButton.setStyleSheet("ctkCollapsibleButton")
        self.mainCollapsibleButton.text = "PointSearch"
        self.layout.addWidget(self.mainCollapsibleButton)
        self.mainFormLayout = qt.QFormLayout(self.mainCollapsibleButton)

        # Add Fiducial Point Button
        self.addPointButton = qt.QPushButton("Add Point")
        self.addPointButton.setStyleSheet("QPushButton")
        self.addPointButton.connect('clicked(bool)', self.onAddPointButtonClick)

        # Lock Point Button
        self.lockPointButton = qt.QPushButton("Unlock Points")
        self.lockPointButton.setStyleSheet("QPushButton")
        self.lockPointButton.connect('clicked(bool)', self.onLockPointButtonClick)

        # Find Fiducial Point Button
        self.findPointButton = qt.QPushButton("Find Points")
        self.findPointButton.setStyleSheet("QPushButton")
        self.findPointButton.connect('clicked(bool)', self.onFindPointButtonClick)

        # Add Add/Edit/Find Fiducial Point Buttons to GUI
	self.mainFormLayout.addWidget(createHLayout([self.addPointButton, self.lockPointButton ,self.findPointButton]))

       
        # Create input Volume Selector
        self.inputSelector = slicer.qMRMLNodeComboBox()
        self.inputSelector.nodeTypes = ["vtkMRMLModelNode"]
        self.inputSelector.selectNodeUponCreation = True
        self.inputSelector.addEnabled = False
        self.inputSelector.removeEnabled = False
        self.inputSelector.noneEnabled = False
        self.inputSelector.showHidden = False
        self.inputSelector.showChildNodeTypes = False
        self.inputSelector.setMRMLScene( slicer.mrmlScene )
        self.inputSelector.setToolTip("select the input image")
        self.mainFormLayout.addRow("Input image: ", self.inputSelector)

        # Fiducial Table
        self.tableNode = slicer.vtkMRMLTableNode()
        self.col=self.tableNode.AddColumn()
        self.col.SetName('Name')
        self.col=self.tableNode.AddColumn()
        self.col.SetName('R')
        self.col=self.tableNode.AddColumn()
        self.col.SetName('A')
        self.col=self.tableNode.AddColumn()
        self.col.SetName('S')
        self.col=self.tableNode.AddColumn()
        self.col.SetName('ID')
        self.col=self.tableNode.AddColumn()
        self.col.SetName('Node')
        self.col=self.tableNode.AddColumn()
        self.col.SetName('Visible')
        self.tableNode.SetColumnType('Visible',1)
        self.tableNode.AddEmptyRow()
        self.tableView=slicer.qMRMLTableView()
        self.tableView.setMRMLTableNode(self.tableNode)
        self.mainFormLayout.addRow(self.tableView)

        self.tableNode.AddObserver(self.tableNode.ReferenceAddedEvent, self.onTableAdd)

                     
        # Import Button
        self.importButton = qt.QPushButton("Import Points")
        self.importButton.setStyleSheet("QPushButton")
        self.importButton.connect('clicked(bool)', self.onImportButtonClick)
        self.mainFormLayout.addRow(self.importButton)

        # Export Button
        self.exportButton = qt.QPushButton("Export Points")
        self.exportButton.setStyleSheet("QPushButton")
        self.exportButton.connect('clicked(bool)', self.onExportButtonClick)
        self.mainFormLayout.addRow(self.exportButton)

        # Create main Fiducial node with tag 'F_Main'
        self.inputFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
        self.inputFiducialNode.SetName("F_Main")
        # Lock the node so it can't be modified
        self.inputFiducialNode.LockedOn()
        slicer.mrmlScene.AddNode(self.inputFiducialNode)
        # Observe scene for updates
        self.inputFiducialNode.AddObserver(self.inputFiducialNode.MarkupAddedEvent, self.onFiducialPointAdd)
        self.inputFiducialNode.AddObserver(self.inputFiducialNode.MarkupRemovedEvent, self.onFiducialPointRemove)
        self.inputFiducialNode.AddObserver(self.inputFiducialNode.PointModifiedEvent, self.onFiducialPointModify)

        self.displayNode = self.inputFiducialNode.GetDisplayNode()
        # TODO: pick appropriate defaults
        # 135,135,84
        self.displayNode.SetTextScale(1.)
        self.displayNode.SetGlyphScale(2.)
        self.displayNode.SetGlyphTypeFromString('StarBurst3D')
        self.displayNode.SetColor((1,1,0.4))
        self.displayNode.SetSelectedColor((1,1,0))

        # Clicked markup index is saved here to let the action
        # know which markup needs to be manipulated.
        slicer.clickedMarkupIndex = -1

        # Create a simple menu
        self.menu = qt.QMenu()
        a1 = qt.QAction("Remove", slicer.util.mainWindow())
        a1.connect('triggered()', self.onRemovePointButtonClick)
        self.menu.addAction(a1)
        a2 = qt.QAction("Edit", slicer.util.mainWindow())
        a2.connect('triggered()', self.onEditPointButtonClick)
        self.menu.addAction(a2)
        # Observe Click events on Fiducial points
        self.inputFiducialNode.AddObserver(self.inputFiducialNode.PointClickedEvent, self.onFiducialPointClick) 

    # Updating the table after adding a Fiducial Point
    # Fiducials with tag 'F_Main' are created by 'Add Point' button
    # Fiducials with tag 'F_Import' are created by 'Import Points' button
    # callData contains the unique Fiducial point id number (0-...)
    @vtk.calldata_type(vtk.VTK_INT)
    def onFiducialPointAdd(self, caller, event, callData):
         # Find all Fiducials with the tag 'F_Main'
         fidListMain = slicer.util.getNode('F_Main')
         if type(fidListMain) is type(slicer.vtkMRMLMarkupsFiducialNode()):
           if(fidListMain.GetNumberOfFiducials() > 0 and 'F_Main' in fidListMain.GetNthFiducialLabel(callData)):
             self.modifyTable('F_Main', callData,True)
         # Find all Fiducials with the tag 'F_Import'
         fidListImport = slicer.util.getNode('F_Import')
         if type(fidListImport) is type(slicer.vtkMRMLMarkupsFiducialNode()):
           if(fidListImport.GetNumberOfFiducials() > 0 and 'F_Import' in fidListImport.GetNthFiducialLabel(callData)):
             self.modifyTable('F_Import', callData,True)
         slicer.app.processEvents()
         if(self.lockPointButton.text in 'Unlock Points'):
           print('Fiducial Locked')
           self.inputFiducialNode.LockedOn()
         
    # Adding the Fiducial point data to the table
    # nodeTag contains the Fiducial node tag (e.g. 'F_Main')
    # fId contains the unique Fiducial Point id (e.g. 'F_Main_1')
    def modifyTable(self,nodeTag, fId, addrow):
         ras = [0,0,0]
         self.inputFiducialNode.GetNthFiducialPosition(fId,ras)
         # Add Fiducial data to the table
         self.tableNode.SetCellText(fId,0,self.getFidLabelNumber(fId))
         self.tableNode.SetCellText(fId,1,str(ras[0]))
         self.tableNode.SetCellText(fId,2,str(ras[1]))
         self.tableNode.SetCellText(fId,3,str(ras[2]))
         self.tableNode.SetCellText(fId,4, self.inputFiducialNode.GetNthMarkupID(fId))
         self.tableNode.SetCellText(fId,5,nodeTag)

         # Add empty row after adding a point
         if(addrow):
           self.tableNode.AddEmptyRow()

    @vtk.calldata_type(vtk.VTK_INT)
    def onTableAdd(self, caller, event,callData):
         print(self,caller,event,callData)

    # Updating the table after removing a Fiducial Point
    # callData contains the unique Fiducial point id number (0-...)
    @vtk.calldata_type(vtk.VTK_INT)
    def onFiducialPointRemove(self, caller, event, callData):
         self.tableNode.RemoveRow(callData)

    # Update table on editing a Fiducial
    # callData contains the unique Fiducial point id number (0-...)
    @vtk.calldata_type(vtk.VTK_INT)
    def onFiducialPointModify(self, caller, event, callData):
         fidListMain = slicer.util.getNode('F_Main')
         if type(fidListMain) is type(slicer.vtkMRMLMarkupsFiducialNode()):
           if(fidListMain.GetNumberOfFiducials() > 0 and 'F_Main' in fidListMain.GetNthFiducialLabel(callData)):
             self.modifyTable('F_Main', callData,False)
         fidListImport = slicer.util.getNode('F_Import')
         if type(fidListImport) is type(slicer.vtkMRMLMarkupsFiducialNode()):
           if(fidListImport.GetNumberOfFiducials() > 0 and 'F_Import' in fidListImport.GetNthFiducialLabel(callData)):
             self.modifyTable('F_Import', callData,False)

    # Open a menu when clicking on unlocked Fiducial point
    # callData contains the unique Fiducial point id number (0-...)
    @vtk.calldata_type(vtk.VTK_INT)
    def onFiducialPointClick(self, caller, eventId, callData):
        # Get most recent clicked point id
        slicer.clickedMarkupIndex = callData
        print('Open menu on markup '+str(slicer.clickedMarkupIndex))
        # Open menu at cursor position
        self.menu.move(qt.QCursor.pos())
        self.menu.show()
    
    def onImportButtonClick(self):
        self.loadFile()
        print("importButton pressed")

    def onAddPointButtonClick(self):
        # Change Fiducial node name to 'F_Main' (May have changed when importing points)
        self.inputFiducialNode.SetName("F_Main")
        # Start Fiducial Placement Mode in Slicer
        placeModePersistance = 0
        slicer.modules.markups.logic().StartPlaceMode(placeModePersistance)
        self.inputFiducialNode.LockedOff()
        
    def onRemovePointButtonClick(self):
        print("removePointButton pressed on:"+str(slicer.clickedMarkupIndex))
        self.inputFiducialNode.RemoveMarkup(slicer.clickedMarkupIndex)

    def onLockPointButtonClick(self):
        # If the Fiducial nodes are locked, unlock them and vice-versa
        # Locked Fiducial nodes can't be interacted with
        if(self.inputFiducialNode.GetLocked()):
          print("Fiducial Unlocked")
          self.lockPointButton.text = 'Lock Points'
          self.inputFiducialNode.LockedOff()
        else:
          print("Fiducial Locked")
          self.lockPointButton.text = 'Unlock Points'
          self.inputFiducialNode.LockedOn()

    def onEditPointButtonClick(self):
        # Create a new window
        self.window = qt.QWidget()
        self.window.setGeometry(10, 10, 452, 243)
        self.window.setWindowTitle('Edit Point '+self.getFidLabelNumber(slicer.clickedMarkupIndex))

        ras = [0,0,0]
        self.inputFiducialNode.GetNthFiducialPosition(slicer.clickedMarkupIndex,ras)

        # Create a form layout (Format:	Label -> Line)
        # 			e.g. 'R-Position' -> 12.242)
        self.layout = qt.QFormLayout()
        self.layout.setFieldGrowthPolicy(qt.QFormLayout.AllNonFixedFieldsGrow)
        self.layout.setHorizontalSpacing(15)
        self.layout.setVerticalSpacing(25)

        # Create Apply/Cancel button and link to functions
        self.applyButton = qt.QPushButton()
        self.applyButton.setGeometry(qt.QRect(270, 220, 121, 41))
        self.applyButton.setText('Apply')
        self.applyButton.connect('clicked(bool)', self.onApplyButtonClick)
        self.cancelButton = qt.QPushButton()
        self.cancelButton.setGeometry(qt.QRect(130, 220, 121, 41))
        self.cancelButton.setText('Cancel')
        self.cancelButton.connect('clicked(bool)', self.onCancelButtonClick)

        # Create the labels and text fields
        self.editFIdLine = qt.QLineEdit()
        self.editFIdLine.setGeometry(qt.QRect(130, 20, 261, 41))
        self.editFIdLine.setText(self.getFidLabelNumber(slicer.clickedMarkupIndex))
        self.editFIdLabel = qt.QLabel()
        self.editFIdLabel.setGeometry(qt.QRect(10, 20, 111, 41))
        self.editFIdLabel.setText('Fiducial Name:')

        self.editFRLine = qt.QLineEdit()
        self.editFRLine.setGeometry(qt.QRect(130, 70, 261, 41))
        self.editFRLine.setText(str(ras[0]))
        self.editFRLabel = qt.QLabel()
        self.editFRLabel.setGeometry(qt.QRect(10, 70, 111, 41))
        self.editFRLabel.setText('R-Position:')

        self.editFALine = qt.QLineEdit()
        self.editFALine.setGeometry(qt.QRect(130, 120, 261, 41))
        self.editFALine.setText(str(ras[1]))
        self.editFALabel = qt.QLabel()
        self.editFALabel.setGeometry(qt.QRect(10, 120, 111, 41))
        self.editFALabel.setText('A-Position:')

        self.editFSLine = qt.QLineEdit()
        self.editFSLine.setGeometry(qt.QRect(130, 170, 261, 41))
        self.editFSLine.setText(str(ras[2]))
        self.editFSLabel = qt.QLabel()
        self.editFSLabel.setGeometry(qt.QRect(10, 170, 111, 41))
        self.editFSLabel.setText('S-Position:')

        # Add the label+text field to the layout
        self.layout.setWidget(0, qt.QFormLayout.LabelRole, self.editFIdLabel)
        self.layout.setWidget(0, qt.QFormLayout.FieldRole, self.editFIdLine)
        self.layout.setWidget(1, qt.QFormLayout.LabelRole, self.editFRLabel)
        self.layout.setWidget(1, qt.QFormLayout.FieldRole, self.editFRLine)
        self.layout.setWidget(2, qt.QFormLayout.LabelRole, self.editFALabel)
        self.layout.setWidget(2, qt.QFormLayout.FieldRole, self.editFALine)
        self.layout.setWidget(3, qt.QFormLayout.LabelRole, self.editFSLabel)
        self.layout.setWidget(3, qt.QFormLayout.FieldRole, self.editFSLine)

        # Create a layout for the two buttons (so they are next to eachother)
        self.horizontalLayout = qt.QHBoxLayout()
        self.horizontalLayout.setSpacing(10)
        self.horizontalLayout.addWidget(self.applyButton)
        self.horizontalLayout.addWidget(self.cancelButton)

        # Add the button layout to the main layout
        self.layout.setLayout(4, qt.QFormLayout.FieldRole, self.horizontalLayout)

        # Set the window layout to our created layout and open the window at the cursor
        self.window.setLayout(self.layout)
        self.window.move(qt.QCursor.pos())
        self.window.show()
        self.inputFiducialNode.LockedOn()
        print("editPointButton pressed")

    # When the 'Apply' button is pressed on the 'Edit'-Window
    def onApplyButtonClick(self):
        ras = [0,0,0]
        self.inputFiducialNode.GetNthFiducialPosition(slicer.clickedMarkupIndex,ras)

        # Extract the Node name (e.g. 'F_Main')
        fidNode = self.inputFiducialNode.GetNthFiducialLabel(slicer.clickedMarkupIndex).split('-', 1)[0]

        print('BEFORE',self.inputFiducialNode.GetNthFiducialLabel(slicer.clickedMarkupIndex),ras[0],ras[1],ras[2])

        # Save the new values and format them (original .text is in unicode format -> needs to be encoded to ascii)
        # RAS-values need to be float-casted
        self.newFId, self.newFR, self.newFA, self.newFS = self.editFIdLine.text.encode('ascii','ignore'),float(self.editFRLine.text.encode('ascii','ignore')),float(self.editFALine.text.encode('ascii','ignore')),float(self.editFSLine.text.encode('ascii','ignore'))

        print('AFTER', fidNode+'-'+self.newFId, self.newFR, self.newFA, self.newFS)

        # Set the Fiducial values to the new ones
        self.inputFiducialNode.SetNthFiducialPosition(slicer.clickedMarkupIndex,self.newFR,self.newFA,self.newFS)
        self.inputFiducialNode.SetNthFiducialLabel(slicer.clickedMarkupIndex,fidNode+'-'+self.newFId)

        # Update the table to show the new values
        self.modifyTable(fidNode, slicer.clickedMarkupIndex,False)
        self.window.close()
        self.inputFiducialNode.LockedOff()
        print('Applied')

    # When the 'Cancel' button is pressed on the 'Edit'-Window
    def onCancelButtonClick(self):
        self.inputFiducialNode.LockedOff()
        self.window.close()
        print('Canceled')

    def onFindPointButtonClick(self):
        print("findPointButton pressed")

    def onExportButtonClick(self):
        print("exportButton pressed")

    # Takes the label of a point (e.g. 'F_Main-XYZ') and returns the Number (here: XYZ)
    def getFidLabelNumber(self, fId):
        retStr = self.inputFiducialNode.GetNthFiducialLabel(fId).split('-', 1)[-1]
        return retStr

    # Importing Fiducial points from a text file
    # Currently imports a text file in the SimPack format
    # 		Markername X Y Z (separated by whitespaces)
    def loadFile(self):
        # Creating a file dialog to navigate to the text file
        root = tk.Tk()
        root.withdraw()
        file_path = tkFileDialog.askopenfilename()
        try:
          with io.open(file_path, 'r', encoding= 'utf-16') as f:
            # Skip first line (Required for SimPack text files since they use a header line)
            next(f)
            self.inputFiducialNode.SetName('F_Import')
            # float-cast the content and multiply by 1000 to offset the scale used in SimPack
            for i in f:
              # Splits the line into 4 values marker=[ID,X,Y,Z]
              marker = i.rstrip('\n').split()
              # Skip cast for the first entry (contains the ID)
              marker_xyz = [float(val) for val in marker[1:]]
              marker_xyz[:] = [x * 1000 for x in marker_xyz]
              self.inputFiducialNode.AddFiducial(marker_xyz[0],marker_xyz[1],marker_xyz[2])
              self.inputFiducialNode.SetNthFiducialLabel(self.inputFiducialNode.GetNumberOfFiducials()-1,'F_Import-'+marker[0])
              self.modifyTable('F_Import', self.inputFiducialNode.GetNumberOfFiducials()-1,False)
        except IOError as e:
          print('File not found or cancelled')
