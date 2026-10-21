try{for(const key of ['theme','accent','density']){const value=localStorage.getItem('musictag-'+key);if(value)document.documentElement.dataset[key]=value}}catch{}
