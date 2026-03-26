function [ErrT]=f_errT(Tref,Tcomp)
    Ntheta=size(Tref,3);
    ErrT=zeros(Ntheta,1);
    for ti=1:Ntheta
        T_Ref_ti=Tref(:,:,ti); T_Comp_ti=Tcomp(:,:,ti);
        ErrT(ti)=sqrt(sum(abs(T_Ref_ti(:)-T_Comp_ti(:)).^2)./sum(abs(T_Ref_ti(:)).^2));
    end
end