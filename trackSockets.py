structure = 0

def analyzeInstruction(method, instruction, register):
    print instruction.opcode(), instruction.parameters()
    
    parameterIndex = instruction.parameters().index(register)
    
    if 'invoke' in instruction.opcode():
        _, methodObject = instruction.classAndMethodByStructure(structure)
        
        if parameterIndex == 0:
            instruction.markAsSink()
            return
        
        print 'MethodObject: '
        print methodObject

        # attempt to find the method used within the apk
        if not (methodObject is None):
            print 'Information is used in method call defined in apk'
            print 'Tracking recursively.....'

            parameterRegister = 'v' + str(methodObject.numberOfLocalRegisters() + parameterIndex)
            trackFromCall(methodObject, parameterRegister, 0)
                
            # Parameter p* is tainted in method instructionMethod, taint it and continue tracking
        else:
            # method is not defined within APK
            print 'Method', methodObject, 'not found'

    elif 'if-' in instruction.opcode():
        print 'Register is used in if statement'
    
    elif 'put' in instruction.opcode():
        print 'Value is put in field'
        #Value is put inside array, 'aput'
        #Value is put in instance field, 'iput'
        #Value is put in static field, 'sput'
        
    elif 'return' in instruction.opcode():
        print 'Value was returned. Looking for usages of this function' 
        
        trackUsages(method.memberOf().name(), method.name())
        
    elif 'move' in instruction.opcode():
        print 'move'
        #Value is moved into other register, 'move'
        
    else:
        print 'Unknown operation performed'


def trackFromCall(method, blockIdx, instructionIdx):
    resultInstruction = method.blocks()[blockIdx].instructions()[instructionIdx]
    if resultInstruction.opcode() in ['move-result-object', 'move-result', 'move-result-wide']:
        register = resultInstruction.parameters()[0]
    else:
        print "No move-result instruction was found for", method.blocks()[blockIdx].instructions()[instructionIdx]
        return
        
    
    print '>', method.name()
    print 'Tracking the result in register', register
    
    instructionIdx += 1 # move the pointer to the instruction after the move-result
    for block in method.blocks()[blockIdx:]:
        startIdx = instructionIdx if block == method.blocks()[blockIdx] else 0
        for instruction in block.instructions()[startIdx:]:
            if register in instruction.parameters():
                
                if instruction.opcode() in ['move-result-object', 'move-result', 'move-result-wide']:
                    return # register is overwritten
                
                analyzeInstruction(method, instruction, register)
                
    print