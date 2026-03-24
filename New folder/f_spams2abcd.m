function [T]=f_spams2abcd(S_SPAM,theta_deg)
    Ntheta=length(theta_deg);
    T=zeros(4,4,Ntheta);
    ZZ=eye(4); YY=eye(4);
    I=eye(2);
    for ti=1:Ntheta
        ZZ(3,3)=cosd(theta_deg(ti)); ZZ(4,4)=secd(theta_deg(ti));
        YY(3,3)=1/ZZ(3,3); YY(4,4)=1/ZZ(4,4);
        hv2xy=diag([cosd(theta_deg(ti)),1,cosd(theta_deg(ti)),1]);
        xy2hv=diag([secd(theta_deg(ti)),1,secd(theta_deg(ti)),1]);
        S_HV=S_SPAM(:,:,ti);
        S_XY=hv2xy*S_HV*xy2hv;
        s11=S_XY(1:2,1:2); s21=S_XY(3:4,1:2); s12=S_XY(1:2,3:4); s22=S_XY(3:4,3:4);
        T_Meas_ti=YY*([I+s11,s12;I-s11,-s12]/[s21,I+s22;s21,-I+s22])*ZZ;  
        T(:,:,ti)=T_Meas_ti;
    end
end