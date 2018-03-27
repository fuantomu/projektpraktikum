from __main__ import vtk, qt, ctk, slicer
from copy import deepcopy
import os, re
import sitkUtils, sys
from slicer.ScriptedLoadableModule import *
import Tkinter as tk, tkFileDialog
import time
import io

class pointSearch2(ScriptedLoadableModule ):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        # Interface Captions
        parent.title        = "pointSearch2"
        parent.categories   = ["VisSim2"]
        parent.dependencies = []
        parent.contributors = [ ""  ]
        parent.helpText     =   ""
        parent.acknowledgementText = " "
        self.parent = parent
 


''' ========================= TODO ===============
- Find a way to decrement the global Fiducial point id after removing one
- Change the opacity of unselected models
- Let the 'Export Points' button export the current Fiducial points in a Slicer-readable? fcsv file
- Let the user set a name when adding a Point? (Open a window after placing)


- Implement a Find Points method
=================================================='''
#                           Main Widget
#===================================================================
class pointSearch2Widget(ScriptedLoadableModuleWidget):
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

        # Create main collapsible Button 
        self.mainCollapsibleButton = ctk.ctkCollapsibleButton()
        self.mainCollapsibleButton.setStyleSheet("ctkCollapsibleButton")
        self.mainCollapsibleButton.text = "PointSearch2"
        self.layout.addWidget(self.mainCollapsibleButton)
        self.mainFormLayout = qt.QFormLayout(self.mainCollapsibleButton)

        # Find Fiducial Point Button
        self.findPointButton = qt.QPushButton("Find Points")
        self.findPointButton.setStyleSheet("QPushButton")
        self.findPointButton.connect('clicked(bool)', self.onFindPointButtonClick)

        # Add Find Fiducial Point Buttons to GUI
	self.mainFormLayout.addRow(self.findPointButton)

       
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
        self.inputFiducialNode.CreateDefaultDisplayNodes()
        slicer.mrmlScene.AddNode(self.inputFiducialNode)
        # Observe scene for updates
        self.inputFiducialNode.AddObserver(self.inputFiducialNode.MarkupAddedEvent, self.onFiducialPointAdd)
        self.inputFiducialNode.AddObserver(self.inputFiducialNode.MarkupRemovedEvent, self.onFiducialPointRemove)

        # Create import Fiducial node with tag 'F_Import'
        self.importFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
        self.importFiducialNode.SetName("F_Import")
        self.importFiducialNode.CreateDefaultDisplayNodes()
        slicer.mrmlScene.AddNode(self.importFiducialNode)
        # Observe scene for updates
        self.importFiducialNode.AddObserver(self.importFiducialNode.MarkupAddedEvent, self.onFiducialPointAdd)
        self.importFiducialNode.AddObserver(self.importFiducialNode.MarkupRemovedEvent, self.onFiducialPointRemove)

        # Fiducial Table
        self.tableNode = slicer.qSlicerSimpleMarkupsWidget()
        self.tableNode.setMRMLScene(slicer.mrmlScene)
        self.tableNode.jumpToSliceEnabled = True
        self.tableNode.setCurrentNode(self.inputFiducialNode)
        self.mainFormLayout.addRow(self.tableNode)

        # Clicked markup index is saved here to let the action know which markup needs to be manipulated.
        slicer.clickedMarkupIndex = -1

        # Create a simple menu
        self.menu = qt.QMenu()
        a1 = qt.QAction("Edit", slicer.util.mainWindow())
        a1.connect('triggered()', self.onEditPointButtonClick)
        self.menu.addAction(a1)
        # Observe Click events on Fiducial points
        self.inputFiducialNode.AddObserver(self.inputFiducialNode.PointClickedEvent, self.onFiducialPointClick) 
        self.importFiducialNode.AddObserver(self.importFiducialNode.PointClickedEvent, self.onFiducialPointClick) 

    # Updating the table after adding a Fiducial Point
    # callData contains the unique Fiducial point id number (0-...)
    @vtk.calldata_type(vtk.VTK_INT)
    def onFiducialPointAdd(self, caller, event, callData):
         print('Point Added: '+str(callData))
         # Let slicer process each point instead of all at once
         slicer.app.processEvents()

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

    # Updating the table after removing a Fiducial Point
    def onFiducialPointRemove(self, caller, event):
        print('Point Removed')
    
    def onImportButtonClick(self):
        self.loadFile()
        print("importButton pressed")

    def onEditPointButtonClick(self):
        # Create a new window
        self.window = qt.QWidget()
        self.window.setGeometry(10, 10, 452, 243)
        self.window.setWindowTitle('Edit Point '+self.tableNode.currentNode().GetNthFiducialLabel(slicer.clickedMarkupIndex))

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
        self.editFIdLine.setText(self.tableNode.currentNode().GetNthFiducialLabel(slicer.clickedMarkupIndex))
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
        print("editPointButton pressed")

    # When the 'Apply' button is pressed on the 'Edit'-Window
    def onApplyButtonClick(self):
        ras = [0,0,0]
        self.tableNode.currentNode().GetNthFiducialPosition(slicer.clickedMarkupIndex,ras)

        print('BEFORE',self.inputFiducialNode.GetNthFiducialLabel(slicer.clickedMarkupIndex),ras[0],ras[1],ras[2])

        # Save the new values and format them (original .text is in unicode format -> needs to be encoded to ascii)
        # RAS-values need to be float-casted
        self.newFId, self.newFR, self.newFA, self.newFS = self.editFIdLine.text.encode('ascii','ignore'),float(self.editFRLine.text.encode('ascii','ignore')),float(self.editFALine.text.encode('ascii','ignore')),float(self.editFSLine.text.encode('ascii','ignore'))

        print('AFTER', self.newFId, self.newFR, self.newFA, self.newFS)

        # Set the Fiducial values to the new ones
        self.tableNode.currentNode().SetNthFiducialPosition(slicer.clickedMarkupIndex,self.newFR,self.newFA,self.newFS)
        self.tableNode.currentNode().SetNthFiducialLabel(slicer.clickedMarkupIndex,self.newFId)

        self.window.close()
        print('Applied')

    # When the 'Cancel' button is pressed on the 'Edit'-Window
    def onCancelButtonClick(self):
        self.window.close()
        print('Canceled')

    def onFindPointButtonClick(self):
        print("findPointButton pressed")

    def onExportButtonClick(self):
        print("exportButton pressed")

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
            # float-cast the content and multiply by 1000 to offset the scale used in SimPack
            for i in f:
              # Splits the line into 4 values marker=[ID,X,Y,Z]
              marker = i.rstrip('\n').split()
              # Skip cast for the first entry (contains the ID)
              marker_xyz = [float(val) for val in marker[1:]]
              marker_xyz[:] = [x * 1000 for x in marker_xyz]
              self.importFiducialNode.AddFiducial(marker_xyz[0],marker_xyz[1],marker_xyz[2])
              self.importFiducialNode.SetNthFiducialLabel(self.importFiducialNode.GetNumberOfFiducials()-1,marker[0])
          self.tableNode.setCurrentNode(self.importFiducialNode)
        except (IOError,TypeError):
          print('File not found or cancelled')
        
