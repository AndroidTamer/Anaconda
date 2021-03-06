import sys, re, time

sys.path.append('androguard')

from androlyze import *

# enum class with opcodes as fields
class InstructionType :
    NONE = -1
    NOP = 0
    MOVERESULT = 1
    MOVE = 2
    RETURN = 3
    IF = 4
    ARRAYGET = 5
    FIELDGET = 6
    STATICGET = 7
    ARRAYPUT = 8
    FIELDPUT = 9
    STATICINVOKE = 10
    INVOKE = 11
    CONST = 12
    NEWINSTANCE = 13
    NEWARRAY = 14
    CONVERSION = 15
    INSTANCEOF = 16
    ARRAYLENGTH = 17
    OPERATION = 18
    
    
def parseOpcode(opcode):
    if 'nop' in opcode:
        return InstructionType.NOP
    elif 'move-result' in opcode:
        return InstructionType.MOVERESULT
    elif 'move' in opcode:
        return InstructionType.MOVE
    elif 'return' in opcode:
        return InstructionType.RETURN
    elif 'if-' in opcode:
        return InstructionType.IF
    elif 'aget' in opcode:
        return InstructionType.ARRAYGET
    elif 'iget' in opcode:
        return InstructionType.FIELDGET
    elif 'sget' in opcode:
        return InstructionType.STATICGET
    elif 'aput' in opcode:
        return InstructionType.ARRAYPUT
    elif 'put' in opcode:
        return InstructionType.FIELDPUT
    elif 'invoke-static' in opcode:
        return InstructionType.STATICINVOKE
    elif 'invoke' in opcode:
        return InstructionType.INVOKE
    elif 'const' in opcode:
        return InstructionType.CONST
    elif 'new-instance' in opcode:
        return InstructionType.NEWINSTANCE
    elif 'new-array' in opcode:
        return InstructionType.NEWARRAY
    elif '-to-' in opcode:
        return InstructionType.CONVERSION
    elif 'instance-of' in opcode:
        return InstructionType.INSTANCEOF
    elif 'array-length' in opcode:
        return InstructionType.ARRAYLENGTH
    elif any(instruction in opcode for instruction in ['add-', 'sub-', 'mul-', 'div-', 'rem-', 'and-', 'or-', 'xor-',
                                                       'shl-', 'shr-', 'ushr-']):
        return InstructionType.OPERATION
    else:
        return InstructionType.NONE

# variables for parsing
classParse = '(\[*L[\w/\$_]*;)'
typeParse = '(\[*L[\w/\$_]*;|\[*[VZBSCIJFD])'
whitespaceParse = '[\s]*'


# parse the last argument of a function call
def parseInvoke(call) :    
    match = re.match(typeParse + '->(.*)', call)
    if match == None:
        print 'error (parseInvoke): ', call
        return '', ''
    
    return match.group(1), match.group(2)

def parseFieldGet(call) :
    #if call != '' and call[0] == '[':
    #    return '', ''
    # ^ ???
    
    match = re.match(typeParse + '->([\w\$_]*)' + whitespaceParse + typeParse, call)
    if match == None:
        print 'error (parseFieldGet): ', call
        return '', '', ''
    
    return match.group(1), match.group(2), match.group(3)

# replace 'v1 ... v3' with 'v1', 'v2', 'v3'
def replaceRange(parameters):
    match = re.match('v([\d]+)' + whitespaceParse + '\.\.\.' + whitespaceParse + 'v([\d]+)', parameters[0])
    if match == None:
        print 'error (replaceRange(1)): ', parameters
        return
    
    firstInt = int(match.group(1))
    secondInt = int(match.group(2))
    
    if secondInt < firstInt or firstInt == None or secondInt == None:
        print 'error  (replaceRange(2)): ', parameters
        return
    
    # remove first 'ranged' parameter
    parameters.pop(0)
    
    for number in range(firstInt, secondInt + 1):
        parameters.insert(number - firstInt, 'v' + str(number))
        

# class containing information about a single construction
class Instruction:
    
    def __init__(self, instruction, block, index):        
        self.d_instruction = instruction
        self.d_parameters = [arg.strip() for arg in instruction.get_output().split(',')]
        self.d_isSink = False
        self.d_type = parseOpcode(instruction.get_name())
        self.d_block = block
        self.d_index = index
        
       
        
        # if the argument is a range convert it
        if len(self.d_parameters) > 0 and '...' in self.d_parameters[0]:
            replaceRange(self.d_parameters)
        
        # if this instruction is a function call parse the function (there is also something like invoke-quick?)
        if self.d_type == InstructionType.INVOKE or self.d_type == InstructionType.STATICINVOKE:
            calledClass, calledMethod = parseInvoke(self.d_parameters[-1]) 
            self.d_parameters[-1] = calledClass
            self.d_parameters.append(calledMethod)
        elif self.d_type in [InstructionType.FIELDGET, InstructionType.STATICGET, InstructionType.FIELDPUT]:
            calledClass, calledField, type = parseFieldGet(self.d_parameters[-1])
            self.d_parameters[-1] = calledClass
            self.d_parameters += [calledField, type] 
        
    # androguard instruction object
    def instruction(self):
        return self.d_instruction
    
    # indices inside the Method and Block object
    def indices(self):
        return self.d_block.index(), self.d_index
    
    # type of instruction, e.g. 'invoke-virtual'
    def opcode(self):
        return self.d_instruction.get_name()
    
    # the possible next instructions after this one
    def nextInstructions(self):
        return self.d_block._nextInstructions(self.d_index)
    
    # type of instruction as int
    def type(self):
        return self.d_type
    
    # mark this instruction as being a sink    
    def markAsSink(self):
        self.d_isSink = True
        
    # method this instruction belongs to
    def method(self):
        return self.d_block.method()
        
    # is this instruction a sink
    def isSink(self):
        return self.d_isSink
    
    # parameters of opcode, e.g. registers, and other things like method to call
    def parameters(self):
        return self.d_parameters
    
    # androguard's smali
    def smali(self, prepend = ''):
        return prepend + self.__str__() + '\n'
        
    # the name of the class and method this instruction is calling
    def classAndMethod(self):
        if self.d_parameters > 1:
            return self.d_parameters[-2], self.d_parameters[-1]
        
        return None, None
    
    # the Class object and Method object this instruction is calling (deprecated)
    def classAndMethodByStructure(self, structure):  
        classObject = structure.classByName(self.d_parameters[-2])
        if classObject is None:
            return None, None
        
        return classObject, classObject.methodByName(self.d_parameters[-1])
    
    # the Class objects and Method objects this instruction is possibly calling (possibly due to inheritance)
    def classesAndMethodsByStructure(self, structure):       
        classObject = structure.classByName(self.d_parameters[-2])  
        # If the classObject is None the class is not defined in the APK or inherited from     
        if classObject is None:
            return [[None, None]]
        
        # is it a static call that's executed virtually
        methodObject = classObject.methodByName(self.d_parameters[-1])
        
        # A static method is virtual if a class does not define it itself
        virtualStatic = 'invoke-static' in self.opcode() and methodObject is None
        
        # Virtual invoke:
        if 'invoke-virtual' in self.opcode() or 'invoke-interface' in self.opcode() or virtualStatic:
            classes = [classObject] + classObject.subClasses()
        
            classesAndMethods = []
        
            # If this class is not defined in the APK we still need to track the method
            if classObject.dvmClass() is None:
                classesAndMethods.append([None, None])
        
            for classObject in classes:
                method = classObject.methodByName(self.d_parameters[-1])
                if not (method is None):
                    classesAndMethods.append([classObject, method])
                
            return classesAndMethods
        # Non virtual invoke:
        else:
            # If the class is not defined the APK return
            if classObject.dvmClass() is None:
                return [[None, None]]
        
            superClass = classObject.superClass()
            
            # A call to the superClass which is not defined in the APK
            if 'invoke-super' in self.opcode() and superClass.dvmClass() is None:
                return [[None, None]]
            # A call to the superClass which is defined in the APK
            elif 'invoke-super' in self.opcode():
                superMethodObject = superClass.methodByName(self.d_parameters[-1])
                # TODO: this should really return look deeper at other superClasses when the method can't be found
                if superMethodObject is None:
                    return [[None, None]]
                
                return [[superClass, superMethodObject]]
            # A call to a direct function
            else:
                if methodObject is None:
                    print 'error: couldn\'t find', self.d_parameters[-1], 'in', self.d_parameters[-2]
                    return [[None, None]]
                return [[classObject, methodObject]]
        

    
    def __str__(self):
        return self.opcode() + str(self.d_parameters)
        
# class containing information about a single block (for example all the different scopes in a method)
class Block:
    def __init__(self, block, method, index):
        self.d_block = block
        self.d_index = index
        self.d_method = method
        
        self.d_instructions = []
        self.d_logicalNextBlocks = []
        
        self.d_number = ''
        #for dvmBlock in self.d_block.get_next():
        #   self.d_logicalNextBlocks.append(Block(dvmBlock[2], method, 0))
        
        for instructionIdx, instruction in enumerate(block.get_instructions()):
            self.d_instructions.append(Instruction(instruction, self, instructionIdx))
    
    # number is a string which uniquely identifies a block in a logical manner
    def number(self):
        return self.d_number
    
    # only used by Method
    def addNextBlock(self, logicalNextBlock):
        #numberOfBlock = len(self.d_logicalNextBlocks)
        
        self.d_logicalNextBlocks.append(logicalNextBlock)
        #if logicalNextBlock.d_number == '':
        #  logicalNextBlock.d_number = self.d_number + '.' + str(numberOfBlock)

    # the possible next instructions after this one
    def _nextInstructions(self, index):
        instructions = []
        
        # is it the last instruction?
        if len(self.d_instructions) == index + 1:
            for block in self.d_logicalNextBlocks:
                instructions.append(block.instructions()[0])
        else:
            instructions.append(self.d_instructions[index + 1])
            
        return instructions
        
    # logical next block
    def nextBlocks(self):
        return self.d_logicalNextBlocks
        
    # androguard block
    def block(self):
        return self.d_block
    
    # method this block belongs to
    def method(self):
        return self.d_method
    
    # index inside the Method object
    def index(self):
        return self.d_index
        
    # Instruction objects within this block
    def instructions(self):
        return self.d_instructions
        
    # androguard's smali  
    def smali(self, prepend = ''):
        code = ''
        for instruction in self.d_instructions:
            code += instruction.smali(prepend)
          
        return code
    
    def __str__(self):
        return ''

# class containing information about a single method
class Method:
    def __init__(self, methodInfo, classObject):
        self.d_class = classObject
        self.d_method = methodInfo
        self.d_blocks = []
        self.d_name = methodInfo.get_method().get_name() + methodInfo.get_method().get_descriptor()
        
        for blockIdx, dvmBlock in enumerate(methodInfo.get_basic_blocks().get()):
            block = Block(dvmBlock, self, blockIdx)
            block.d_number = str(blockIdx)
            self.d_blocks.append(block)
           
        # make sure all blocks know what their next block is
        for block in self.d_blocks:
            nextDvmBlockList = block.block().get_next()
            if nextDvmBlockList == []:
                continue
            for nextBlock in self.d_blocks:
                for nextDvmBlock in nextDvmBlockList:
                    if nextBlock.block() is nextDvmBlock[2]:
                        block.addNextBlock(nextBlock)        
                   
        # find catch blocks and make sure they are next to a try block
        previousBlock = None
        for block in self.d_blocks:
            for instruction in block.instructions():
                if instruction.opcode() == 'move-exception' and not (previousBlock is None):
                    previousBlock.addNextBlock(block)
                    break
                elif instruction.opcode() == 'move-exception':
                    print 'error: a catch block is first block of method ', self
                    break
            
            previousBlock = block
        
            
        

    # MethodAnalysis object
    def method(self):
        return self.d_method
    
    # name of the function
    def name(self):
        return self.d_name
    
    # Class object this method is a member of
    def memberOf(self):
        return self.d_class
    
    # first instruction of this method
    def firstInstruction(self):
        if self.hasCode():
            return self.d_blocks[0].instructions()[0]
        
        return None

    # indices in the list of Block object and the list of Instruction objects within that, where the given method is called
    def calledInstructionsByMethodName(self, className, methodName):
        instructions = []
        for block in self.d_blocks:
            for instruction in block.instructions():
                if instruction.type() in [InstructionType.INVOKE, InstructionType.STATICINVOKE] and className in instruction.parameters()[-2] and methodName in instruction.parameters()[-1]:
                    instructions.append(instruction)
        
        return instructions
    
    # indices in the list of Block object and the list of Instruction objects within that, where the given field is accessed
    def calledInstructionsByFieldName(self, className, fieldName):
        instructions = []
        for block in self.d_blocks:
            for instruction in block.instructions():
                if instruction.type() in [InstructionType.FIELDGET, InstructionType.STATICGET] and className in instruction.parameters()[-3] and fieldName in instruction.parameters()[-2]:                
                    instructions.append(instruction)
        
        return instructions
                
    # number of registers e.g. v1, v2, v3 etc (this includes the parameters)
    def numberOfRegisters(self):
        if self.hasCode():
            return self.d_method.get_method().get_code().get_registers_size()
        else:
            return None    
        
    # number of parameters
    def numberOfParameters(self):
        if self.hasCode():
            return self.d_method.get_method().get_code().get_ins_size()
        else:
            return None
        
    # number of registers without the parameters
    def numberOfLocalRegisters(self):
        if self.hasCode():
            return self.numberOfRegisters() - self.numberOfParameters()
        else:
            return 0
    
    # does the function contain code
    def hasCode(self):
        return self.d_method.get_method().get_code() is not None
    
    # list of Block objects
    def blocks(self):
        return self.d_blocks
    
    # java source code
    def sourceCode(self):
        try:
            return self.d_method.get_method().get_source()
        except AttributeError:
            return 'Error while retrieving java source code'
      
    # androguard's smali  
    def smali(self, prepend = ''):
        code = prepend + self.name() + ':\n'
        for block in self.d_blocks:
            code += '\n'
            code += block.smali(prepend + '    ')
          
        return code
    
    def __str__(self):
        return self.name()

# class containing information about a single class
class Class:    
    # if jvmClass is None we can't find the class
    def __init__(self, jvmClass = None, analysis = None):
        self.d_class = jvmClass
        self.d_methods = {}
        
        if(jvmClass is None):
            self.d_initialized = True
        else:
            self.d_initialized = False
        
        self.d_analysis = analysis
        
        self.d_superClass = None
        self.d_subClasses = []
        self.d_haveRecursiveSearched = False

    # add subclasses this class has
    def addSubclass(self, subClasses):
        self.d_subClasses.append(subClasses) # TODO: duplicates?

    # subClasses of this class
    def subClasses(self):
        if self.d_haveRecursiveSearched == False:
            self._addSubClassesRecursively()
            
        return self.d_subClasses
    
    def _addSubClassesRecursively(self):
        self.d_haveRecursiveSearched = True
        
        newList = []
        
        for subClass in self.d_subClasses:
            newList += subClass.subClasses()
            
        self.d_subClasses += newList
        set = {}
        map(set.__setitem__, self.d_subClasses, [])
        self.d_subClasses = set.keys()

    # androguard class
    def dvmClass(self):
        return self.d_class
    
    # source code in java of this class
    def sourceCode(self):
        try:
            return self.dvmClass().get_source()
        except AttributeError:
            return 'Error while retrieving java source code'
      
    # androguard's smali  
    def smali(self):
        code = self.name() + ':\n'
        for _, method in self.methods().items():
            code += '\n'
            code += method.smali('    ')
          
        return code
    
    # superclass of this class
    def superClass(self):
        return self.d_superClass
    
    # set superclass of this class
    def setSuperClass(self, superclass):
        self.d_superClass = superclass
    
    # name of superclass of this class
    def superClassName(self):
        return self.d_class.get_superclassname()
    
    def interfaceNames(self):
        interfacesString = self.d_class.get_interfaces()
        if interfacesString is None:
            return []
        interfacesString = interfacesString.replace('(', '')
        interfacesString = interfacesString.replace(')', '')
        return interfacesString.split(' ')

    # name of the class
    def name(self):
        if self.d_class is None:
            return 'Java API class'
            
        return self.d_class.get_name()
            
    # dictionary containing the Method objects by name
    def methods(self):
        if self.d_initialized == False:
            self._initializeMethods()
            
        return self.d_methods      
    
    # Method object with a certain name
    def methodByName(self, name):
        # if no methods in this class parse them
        if self.d_initialized == False:
            self._initializeMethods()
            
        return self.d_methods.get(name, None)
    
    def __str__(self):
        return self.name()
    
    # initializes the dictionary of Method objects, only called when needed
    def _initializeMethods(self):
        self.d_initialized = True

        for method in self.d_class.get_methods():
            newMethod = Method(self.d_analysis.get_method(method), self)
            self.d_methods[newMethod.name()] = newMethod

# class containing information about an entire APK file
class APKstructure:
    def __init__(self, file):
        _, self.d_dvm, self.d_analysis = AnalyzeAPK(file, False, 'dad')
        
        self.d_classes = {}
        for jvmClass in self.d_dvm.get_classes():
            self.d_classes[jvmClass.get_name()] = Class(jvmClass, self.d_analysis)
           
        # add subclasses to classes
        for _, classObject in self.d_classes.items():
            superClasses = [classObject.superClassName()] + classObject.interfaceNames()

            # loop through all super classes of this class and add this class as subclass
            for superClass in superClasses:
                superClassObject = self.d_classes.get(superClass, None)
                if superClassObject is None:
                    superClassObject = Class()
                    self.d_classes[superClass] = superClassObject
                    
                classObject.setSuperClass(superClassObject)
                superClassObject.addSubclass(classObject)

    # dictionary of Class objects by name
    def classes(self):
        return self.d_classes
    
    # Class object with a certain name
    def classByName(self, name):
        return self.d_classes.get(name, None)
    
    # Method objects in which the given method is called
    def calledMethodsByMethodName(self, className, methodName):
        # search_methods requires regexp's, this makes sure it gets them
        descriptorLoc = methodName.find('(')
        if descriptorLoc == -1:
            descriptor = '.'
        else:
            descriptor = methodName[descriptorLoc:]
            descriptor = descriptor.replace('(', '\(')
            descriptor = descriptor.replace(')', '\)')
            descriptor = descriptor.replace('$', '\$')
            descriptor = descriptor.replace('[', '\[')
            methodName = methodName[0:descriptorLoc]
        
        pathps = self.d_analysis.tainted_packages.search_methods(className, methodName, descriptor)
        methods = []
        for path in pathps:
            # find the Method object that is associated with this path
            location = path.get_src(self.d_dvm.get_class_manager())
            classObject = self.classByName(location[0])
            if classObject is None:
                print 'error couldn\'t find class ', location[0]
                continue
            method = classObject.methodByName(location[1] + location[2])
            if method is None:
                print 'error couldn\'t find method ', location[1] + location[2], ' in class ', location[0]
                continue
            
            methods.append(method)
            
        return methods
    
    # Method objects in which the given field is accessed, descriptor is type
    def calledMethodsByFieldName(self, className, fieldName, descriptor):
        
        field = self.d_analysis.tainted_variables.get_field(className, fieldName, descriptor)
        if field is None:
            return None
            
        pathps = field.get_paths()
        methods = []
        
        for data, methodIdx in pathps:
            
            # we are only interested in field reads
            if data[0] == 'W':
                continue
            
            # find the Method object that is associated with this path
            className, methodName, parameters = self.d_dvm.get_cm_method(methodIdx)
            methodName += parameters[0] + parameters[1]
            
            classObject = self.classByName(className)
            if classObject is None:
                print 'error couldn\'t find class ', className
                continue
            method = classObject.methodByName(methodName)
            if method is None:
                print 'error couldn\'t find method ', methodName, ' in class ', className
                continue
            
            if method not in methods:
                methods.append(method)
            
        return methods
    
    # androguard DalvikVMFormat
    def dvm(self):
        return self.d_dvm
    
    # androguard uVMAnalysis
    def analysis(self):
        return self.d_analysis
    
    def __str__(self):
        return ''
