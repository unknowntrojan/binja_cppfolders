import binaryninja as bn
from binaryninja import BackgroundTaskThread
from binaryninja.binaryview import BinaryView, StringReference, DataVariable
from binaryninja.plugin import PluginCommand
from binaryninja.types import TypeClass, Type
from binaryninja.architecture import Architecture

class InspectInBackground(BackgroundTaskThread):    
    def __init__(self, bv: BinaryView):
        BackgroundTaskThread.__init__(
            self, "Class Sorter - sorting classes...", True)
        self.bv = bv

    def run(self):        
        indexer = "‌"
        filler = "​"
        
        arch = self.bv.arch
        if not isinstance(arch, bn.Architecture):
            print("failed to determine architecture")
            return
        
        self.bv.begin_undo_actions()
        
        self.bv.remove_component("Classes")
        
        cpp_comp = self.bv.create_component("Classes")
            
        # for every vtable, create a folder for it
        # push all functions into the folder, duplicate classes be damned
        for data_var in self.bv.data_vars.values():
            if isinstance(data_var.name, str) and "::vfTable" in data_var.name:
                # {n namespaces}::{class}::vfTable
                dissected_qualifier = data_var.name.split("::")
                
                class_name = dissected_qualifier[-2] + f" ({int(data_var.type.width / 8)})"
                namespaces = dissected_qualifier[:-2]                    

                comp = cpp_comp

                path = "Classes/"
                
                for namespace in namespaces:
                    entry = self.bv.get_component_by_path(path + namespace)
                    if entry is not None:
                        comp = entry
                    else:                        
                        comp = self.bv.create_component(namespace, comp)
                        
                    path += namespace + "/"
                
                entry = self.bv.get_component_by_path(path + class_name)
                if entry is not None:
                    comp = entry
                else:                        
                    comp = self.bv.create_component(class_name, comp)
                
                comp.add_data_variable(data_var)
                
                # TODO add RTTI locators to folder as well
                    
                if data_var.type.type_class == TypeClass.ArrayTypeClass and "void*" in data_var.type.get_string():
                    # entries = int(data_var.type.width / arch.address_size)
                    entries = len(data_var.value)
                    for ref in data_var.code_refs:
                        if not isinstance(ref.function, bn.Function):
                            continue
                        
                        func: bn.Function = ref.function
                        if f"{dissected_qualifier[-2]}" in func.name and "::Constructor" in func.name:
                            # found a constructor! add it to our list.
                            comp.add_function(func)
                            
                            for rref in self.bv.get_code_refs(func.start):
                                # look for thunks
                                ffunc = rref.function
                                
                                if not isinstance(ffunc, bn.Function):
                                    continue
                                
                                if f"{dissected_qualifier[-2]}" in ffunc.name and "::Thunk" in ffunc.name:
                                    comp.add_function(ffunc)
                    
                    for num, entry in enumerate(data_var.value):
                        vfunc = self.bv.get_function_at(entry)
                        if not isinstance(vfunc, bn.Function):
                            continue
                        
                        comp.add_function(vfunc)
                        
                        if "sub" not in vfunc.name:
                            try:
                                func_name = vfunc.name
                                
                                encoded_class_length = num + func_name.count(filler)
                                
                                if entries > encoded_class_length:
                                    # if we are a bigger class, we have authority to rename
                                    # to preserve order.
                                    func_name = func_name.replace(filler, "")
                                    func_name = func_name.replace(indexer, "")
                                    
                                    # fill with spacers
                                    for i in range(entries - num):
                                        func_name = filler + func_name
                                    
                                    # encode actual index
                                    for i in range(num + 1):
                                        func_name = indexer + func_name
                                    
                                    vfunc.name = func_name
                            except:
                                print(f"failed to sort {vfunc.name}")
                                
        self.bv.commit_undo_actions()

        print("sorting finished!")

def inspect(bv: BinaryView):
    if bv.analysis_info.state != 2:
        print(f'Binja analysis still ongoing, please run this plugin only after analysis completes.')
    else:
        background_thread = InspectInBackground(bv)
        background_thread.start()

PluginCommand.register("Sort C++ classes into folders",
                          "Sorts C++ classes into folders in the new symbol view.",
                          inspect)
