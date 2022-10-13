import { useAppSelector } from '../../../hooks/hook';
import "../../../styles.scss";
import { getFOIS3DocumentPreSignedUrl } from '../../../apiManager/services/foiOSSService';
import { useEffect, useState } from 'react';
import { useDispatch } from "react-redux";
import { params } from './types';

function Home() {

  let filepath = "EDU/ABC-2022-091801/email-attachment/557ad265-fa10-4e25-b609-f28cf606cb4d.xlsx";
  const dispatch = useDispatch();
  const user = useAppSelector((state: any) => state.user.userDetail);
  const [presignedUrl, setpresignedUrl] = useState(filepath);


  useEffect(() => {
    // if(filepath)
    // {
          
          let ministryrequestid="20";
          const response = getFOIS3DocumentPreSignedUrl(filepath,ministryrequestid, dispatch)
          response.then((result)=>{                        
                var viwerUrl =   result.data
                if(filepath.toLowerCase().indexOf('.docx') >-1 ||filepath.toLowerCase().indexOf('.doc') >-1 || filepath.toLowerCase().indexOf('.xls') >-1 || filepath.toLowerCase().indexOf('.xlsx')>-1)
                { 
                 viwerUrl =`https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(result.data)}`
                }
                setpresignedUrl(viwerUrl)                        
          })
          console.log("##PresignedUrl:",presignedUrl);
   // }            
},[]);

  return (
    <div className="App">
      <header className="app-header">
        <span className="navbar-text" style={{}}> Hi {user.name || user.preferred_username || ""} </span>
      </header>
    </div>
  );
}

export default Home;
