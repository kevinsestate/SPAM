%% Logistics
clear all
setupPlotDefaults
format compact
fig_cnt=0;
c0=physconst('LightSpeed'); ep0=8.854e-12; mu0=1/c0^2/ep0; eta0=sqrt(mu0/ep0);

%% Extraction
HFSS_Data_Dir='./Extracted_S4P';
theta_deg=(2:2:88).'; Ntheta=length(theta_deg);
S_Fields=zeros(4,4,Ntheta);
S_SPAM=zeros(4,4,Ntheta);
theta_str='theta_inc';
search_pattern=['%*s',' = %fdeg'];
for ei=1:Ntheta
    fname=[HFSS_Data_Dir,'/',num2str(ei),'.s4p'];
    spdata=sparameters(fname);
    spdata.Parameters;
    % pull angle data from HFSS touchstone file
    fid = fopen(fname,'r');    
    cell_input = textscan(fid,'%[^\n]'); 
    text_data = cell_input{1,1};    
    fclose(fid);
    line_number = find(contains(text_data,theta_str));
    line=text_data{line_number}(2:end-1); data_cell=textscan(line,search_pattern);
    theta_deg_tmp=data_cell{1};

    % assign new reference impedance
    z_tmp=s2z(spdata.Parameters,spdata.Impedance);
    Zmat=diag(eta0.*[cosd(theta_deg_tmp),secd(theta_deg_tmp),cosd(theta_deg_tmp),secd(theta_deg_tmp)]);
    R=diag(sqrt(2.*eta0.*[cosd(theta_deg_tmp),secd(theta_deg_tmp),cosd(theta_deg_tmp),secd(theta_deg_tmp)]));
    Ri=diag(1./sqrt(2.*eta0.*[cosd(theta_deg_tmp),secd(theta_deg_tmp),cosd(theta_deg_tmp),secd(theta_deg_tmp)]));
    hv2xy=diag([cosd(theta_deg_tmp),1,cosd(theta_deg_tmp),1]);
    xy2hv=diag([secd(theta_deg_tmp),1,secd(theta_deg_tmp),1]);
    s_E=(z_tmp-Zmat)/(z_tmp+Zmat);
    s_E_tmp=s_E;
    S11p=s_E_tmp(1:2,1:2);
    S12p=s_E_tmp(1:2,3:4);
    S21p=s_E_tmp(3:4,1:2);
    S22p=s_E_tmp(3:4,3:4);
    S11p(2,1)=-S11p(2,1); S11p(1,2)=-S11p(1,2);
    S21p(2,1)=-S21p(2,1); S21p(1,2)=-S21p(1,2);
    S12p(2,1)=-S12p(2,1); S12p(1,2)=-S12p(1,2);
    S22p(2,1)=-S22p(2,1); S22p(1,2)=-S22p(1,2);
    s_E(1:2,1:2)=S22p;
    s_E(3:4,1:2)=S12p;
    s_E(1:2,3:4)=S21p;
    s_E(3:4,3:4)=S11p;
    S_SPAM_tmp=xy2hv*s_E*hv2xy;
%     s_power_wave=Ri*s_E*R;

    % Assign appropriate index
    [~,idx]=min((theta_deg-theta_deg_tmp).^2);
    S_Fields(:,:,idx)=s_E;
    S_SPAM(:,:,idx)=S_SPAM_tmp;

end
save('SPAM_Scat_Mat_erfull_murfull_cutoff.mat','S_SPAM','theta_deg');


