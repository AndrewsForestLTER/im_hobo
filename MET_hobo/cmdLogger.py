# -*- coding: utf-8 -*-
"""
Created on Fri Jul 17 11:09:51 2015

@author: greg.cohn
"""
import os, subprocess

class CmdLogger():    
    
    def setCmd(self,cmd = False):
        """
        """
        if not cmd:
            cmd = self.exe + ' ' + self.input
        
        self.cmd = cmd
        
    def setInput(self, input_param):
        """
        set the input parameter, either a str or a str of a filepath to a file
        """
        self.input = input_param
        
    def setlog(self,log):
        """
        """
        self.log =  log
        
    def runCmd(self):
        """
        """
        FNULL = open(self.log, 'a+')
        FNULL.seek(0,os.SEEK_END)
        subprocess.call(self.cmd, stdout = FNULL, stderr = subprocess.STDOUT)
        FNULL.close()
        
    def dosStripPath(self,log = False):
        """
        """
        if not log:
            log = self.log
            
        with open(log, 'r+') as f:
            lines =  f.readlines()
            
        for i in range(0,len(lines)):
            l = lines[i]            
            
            path,dash,out = l.partition('>')
            if dash is '':
                continue
            
            path = path.rpartition('\\')[-1]+'\\'
            l = path+dash+out
            
            lines[i]=l
            
        with open(log, 'w') as f:
            for l in lines:
                f.write(l)

if __name__ == '__main__':          
    import os
    os.chdir('c://Users//greg.cohn//wkspace//FUSIONtests//fromgui//')
    cmd = CmdLogger()    
    cmd.setlog('./fusion_setup.log')    
    cmd.setCmd('setup.bat')
    cmd.runCmd()
    cmd.dosStripPath()
  